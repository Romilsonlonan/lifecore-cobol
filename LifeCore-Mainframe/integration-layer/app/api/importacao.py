"""
POST /api/apolices/importar
Recebe o arquivo do corretor (CSV, XLSX ou JSON),
converte para o layout fixo CPYAPOL e dispara o ciclo batch.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.apolice import ImportacaoResponse, StatusJobEnum
from app.services.batch_connector import criar_job, disparar_batch
from app.services.conversor import build_flat_file, parse_arquivo

router = APIRouter()

_EXTENSOES_PERMITIDAS = {".csv", ".xlsx", ".xls", ".json"}
_TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/importar",
    response_model=ImportacaoResponse,
    summary="Importar arquivo de apólices",
    description=(
        "O corretor envia um arquivo CSV, XLSX ou JSON com as apólices. "
        "A API converte para layout de largura fixa (CPYAPOL 300 bytes) "
        "e dispara o ciclo batch COBOL (ARQVAL01 → VGCCAP01 → FATURA01…)."
    ),
)
async def importar_apolices(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(..., description="CSV, XLSX ou JSON com as apólices"),
):
    # ── Validações básicas ─────────────────────────────────────────
    ext = Path(arquivo.filename or "").suffix.lower()
    if ext not in _EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=422,
            detail=f"Formato '{ext}' não suportado. Use: {', '.join(_EXTENSOES_PERMITIDAS)}",
        )

    conteudo = await arquivo.read()
    if len(conteudo) > _TAMANHO_MAXIMO_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo maior que 10 MB.")

    # ── Parse → objetos ApoliceInput ──────────────────────────────
    try:
        apolices = parse_arquivo(arquivo.filename, conteudo)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erro ao ler arquivo: {exc}")

    if not apolices:
        raise HTTPException(status_code=422, detail="Arquivo vazio ou sem dados.")

    # ── Gera flat file de largura fixa ────────────────────────────
    flat_content = build_flat_file(apolices)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    flat_path = settings.data_input_dir / f"APOLICE_{timestamp}"
    flat_path.write_text(flat_content, encoding="utf-8")

    # ── Cria job e dispara em background ──────────────────────────
    job_id = criar_job()
    background_tasks.add_task(disparar_batch, job_id, flat_path)

    return ImportacaoResponse(
        job_id=job_id,
        status=StatusJobEnum.PENDENTE,
        arquivo_gerado=str(flat_path),
        total_registros=len(apolices),
        mensagem=(
            f"{len(apolices)} apólice(s) recebida(s). "
            f"Ciclo batch iniciado. Consulte /api/jobs/{job_id}/status"
        ),
    )
