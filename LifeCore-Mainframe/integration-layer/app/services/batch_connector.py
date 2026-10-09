"""
Conector Batch — dispara o ciclo COBOL conforme o ambiente configurado.

batch_connector = "stub"   → simula execução (dev/CI sem COBOL instalado)
batch_connector = "local"  → subprocess com GnuCOBOL compilado
batch_connector = "zowe"   → Zowe CLI, envia dataset e submete JCL no z/OS
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.schemas.apolice import JobStatusResponse, StatusJobEnum

# Registro em memória (em produção substitua por Redis / DB)
_jobs: dict[str, JobStatusResponse] = {}


# ── API pública ────────────────────────────────────────────────────────────


def criar_job() -> str:
    """Cria um novo job e retorna seu ID."""
    job_id = str(uuid.uuid4())[:8].upper()
    _jobs[job_id] = JobStatusResponse(
        job_id=job_id,
        status=StatusJobEnum.PENDENTE,
        inicio=datetime.now(UTC),
    )
    return job_id


def obter_job(job_id: str) -> JobStatusResponse | None:
    return _jobs.get(job_id)


async def disparar_batch(job_id: str, flat_file_path: Path) -> None:
    """
    Dispara a execução em background.
    Não bloqueia o endpoint — usa asyncio.create_task.
    """
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="Iniciando")
    conector = settings.batch_connector

    if conector == "local":
        asyncio.create_task(_executar_local(job_id, flat_file_path))
    elif conector == "zowe":
        asyncio.create_task(_executar_zowe(job_id, flat_file_path))
    else:
        asyncio.create_task(_executar_stub(job_id, flat_file_path))


# ── Conector: stub (simulação) ─────────────────────────────────────────────


async def _executar_stub(job_id: str, flat_file_path: Path) -> None:
    """Simula processamento sem executar COBOL de verdade."""
    await asyncio.sleep(1)
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="ARQVAL01")
    await asyncio.sleep(1)
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="VGCCAP01")
    await asyncio.sleep(1)
    _atualizar(
        job_id,
        StatusJobEnum.CONCLUIDO,
        rc=0,
        etapa="Concluído",
        log="[STUB] Ciclo simulado com sucesso. Arquivo: " + str(flat_file_path),
    )


# ── Conector: local (GnuCOBOL subprocess) ─────────────────────────────────


async def _executar_local(job_id: str, flat_file_path: Path) -> None:
    """
    Copia o flat file para DATA/INPUT/APOLICE e executa ARQVAL01 + VGCCAP01.
    Os demais steps (FATURA01, CONCIL01…) seguem o mesmo padrão.
    """
    load = settings.cobol_load_dir

    # STEP 1 — ARQVAL01
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="ARQVAL01")
    rc, log = await _run(
        str(load / "ARQVAL01"),
        env={
            "LIFECORE_DATA_INPUT_APOLICE": str(flat_file_path),
            "LIFECORE_DATA_OUTPUT_APOLICE": str(settings.data_output_dir / "APOLICE"),
            "LIFECORE_DATA_QUARANTINE_APOLICE": str(
                settings.data_quarantine_dir / "APOLICE"
            ),
        },
    )
    if rc > 8:
        _atualizar(job_id, StatusJobEnum.ERRO, rc=rc, log=log)
        return

    # STEP 2 — VGCCAP01
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="VGCCAP01")
    rc2, log2 = await _run(
        str(load / "VGCCAP01"),
        env={
            "LIFECORE_DATA_OUTPUT_APOLICE": str(settings.data_output_dir / "APOLICE"),
            "LIFECORE_DATA_OUTPUT_CAPITAL": str(settings.data_output_dir / "CAPITAL"),
        },
    )

    status = StatusJobEnum.CONCLUIDO if rc2 <= 4 else StatusJobEnum.ERRO
    _atualizar(job_id, status, rc=rc2, etapa="Concluído", log=log + "\n" + log2)


async def _run(cmd: str, env: dict[str, str]) -> tuple[int, str]:
    """Executa um binário COBOL como subprocess assíncrono."""
    import os

    full_env = {**os.environ, **env}
    proc = await asyncio.create_subprocess_exec(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=full_env,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


# ── Conector: Zowe CLI (z/OS real) ─────────────────────────────────────────


async def _executar_zowe(job_id: str, flat_file_path: Path) -> None:
    """
    1. Faz upload do flat file para o dataset z/OS via Zowe CLI.
    2. Submete o JCL LCIMP01 que inicia o ciclo.
    3. Faz polling do status do job até completar.
    """
    hlq = settings.zos_hlq
    profile = settings.zowe_profile
    dataset = f"{hlq}.DATA.INPUT.APOLICE"

    # Upload do flat file
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="Upload z/OS dataset")
    rc_up, log_up = await _run_zowe(
        [
            "zowe",
            "files",
            "ul",
            "ftds",
            str(flat_file_path),
            dataset,
            "--profile",
            profile,
            "--binary",
        ]
    )
    if rc_up != 0:
        _atualizar(job_id, StatusJobEnum.ERRO, rc=rc_up, log=log_up)
        return

    # Submissão do JCL
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa="Submetendo LCIMP01")
    jcl_dataset = f"{hlq}.JCL(LCIMP01)"
    rc_sub, log_sub = await _run_zowe(
        ["zowe", "jobs", "submit", "ds", jcl_dataset, "--profile", profile]
    )
    if rc_sub != 0:
        _atualizar(job_id, StatusJobEnum.ERRO, rc=rc_sub, log=log_sub)
        return

    # Extrai o JES job ID da saída ("JOB00001" etc.)
    jes_id = _extrair_jes_id(log_sub)
    _atualizar(job_id, StatusJobEnum.EXECUTANDO, etapa=f"Aguardando {jes_id}")

    # Polling
    for _ in range(60):  # até 5 minutos (60 × 5s)
        await asyncio.sleep(5)
        rc_st, log_st = await _run_zowe(
            ["zowe", "jobs", "view", "status", jes_id, "--profile", profile]
        )
        if "OUTPUT" in log_st or "ABEND" in log_st:
            rc_final = 0 if "RC=0000" in log_st else 8
            status = StatusJobEnum.CONCLUIDO if rc_final == 0 else StatusJobEnum.ERRO
            _atualizar(job_id, status, rc=rc_final, log=log_st)
            return

    _atualizar(job_id, StatusJobEnum.ERRO, log="Timeout aguardando job z/OS")


async def _run_zowe(args: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


def _extrair_jes_id(log: str) -> str:
    """Extrai 'JOBxxxxx' da saída do zowe jobs submit."""
    import re

    m = re.search(r"(JOB\d+)", log)
    return m.group(1) if m else "JOBUNKNOWN"


# ── Helpers internos ───────────────────────────────────────────────────────


def _atualizar(
    job_id: str,
    status: StatusJobEnum,
    rc: int | None = None,
    etapa: str | None = None,
    log: str | None = None,
) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    job.status = status
    if rc is not None:
        job.return_code = rc
    if etapa is not None:
        job.etapa_atual = etapa
    if log is not None:
        job.log_resumo = log[:2000]  # limita tamanho
    if status in (StatusJobEnum.CONCLUIDO, StatusJobEnum.ERRO):
        job.fim = datetime.now(UTC)
