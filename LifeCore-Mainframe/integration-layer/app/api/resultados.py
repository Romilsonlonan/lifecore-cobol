"""
GET /api/apolices/resultado/{job_id}
Lê os arquivos de saída do COBOL (válidos + quarentena) e devolve
um resumo estruturado para o corretor.
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path

from app.core.config import settings
from app.schemas.apolice import (
    ApoliceResultado,
    ResultadoImportacaoResponse,
    StatusJobEnum,
)
from app.services.batch_connector import obter_job

router = APIRouter()


@router.get(
    "/resultado/{job_id}",
    response_model=ResultadoImportacaoResponse,
    summary="Resultado do processamento COBOL",
    description=(
        "Disponível após o job atingir status CONCLUIDO. "
        "Lê o arquivo de saída (válidos) e o de quarentena (erros) "
        "gerados pelo COBOL e retorna um resumo para o corretor."
    ),
)
def resultado(job_id: str):
    job = obter_job(job_id.upper())
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    if job.status not in (StatusJobEnum.CONCLUIDO, StatusJobEnum.ERRO):
        raise HTTPException(
            status_code=409,
            detail=f"Job ainda em andamento (status={job.status}). Tente novamente.",
        )

    validos     = _ler_apolices_validas(settings.data_output_dir / "APOLICE")
    quarentena  = _ler_quarentena(settings.data_quarantine_dir / "APOLICE")

    return ResultadoImportacaoResponse(
        job_id=job_id.upper(),
        total_validos=len(validos),
        total_erros=len(quarentena),
        apolices=validos + quarentena,
    )


# ── Leitores de arquivo flat ───────────────────────────────────────────────

def _ler_apolices_validas(path: Path) -> list[ApoliceResultado]:
    """
    Lê o arquivo de saída do ARQVAL01 (registros D1 de 300 chars).
    Extrai número da apólice (pos 3-14) e capital calculado (pos 102-116).
    """
    if not path.exists():
        return []
    resultados = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        if not linha.startswith("D1"):
            continue
        if len(linha) < 116:
            continue
        numero  = linha[2:14].strip()
        cap_raw = linha[101:116].strip()
        try:
            capital = int(cap_raw) / 100 if cap_raw.isdigit() else None
        except ValueError:
            capital = None
        resultados.append(ApoliceResultado(
            numero_apolice=numero,
            status="VALIDO",
            capital_calculado=capital,
        ))
    return resultados


def _ler_quarentena(path: Path) -> list[ApoliceResultado]:
    """
    Lê o arquivo de quarentena do ARQVAL01 (registros D1 de 180 chars).
    Extrai código de erro (pos 29-35) e chave do registro (pos 161-180).
    Layout espelha CPYERRO.cpy.
    """
    if not path.exists():
        return []
    resultados = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        if not linha.startswith("D1"):
            continue
        if len(linha) < 80:
            continue
        codigo_erro = linha[28:35].strip()
        chave       = linha[160:180].strip() if len(linha) >= 180 else ""
        resultados.append(ApoliceResultado(
            numero_apolice=chave or "(sem chave)",
            status="ERRO",
            erro=_descricao_erro(codigo_erro),
        ))
    return resultados


_ERROS: dict[str, str] = {
    "E00001": "CPF do segurado ausente ou inválido",
    "E00002": "CNPJ do estipulante inválido",
    "E00003": "Capital segurado zero ou produto inválido",
    "E00004": "Vigência inválida ou ausente",
    "E00005": "Campo COMP-3 corrompido",
    "E00006": "Apólice duplicada",
    "E00007": "Apólice não encontrada",
    "E00008": "Fatura não encontrada",
}


def _descricao_erro(codigo: str) -> str:
    return _ERROS.get(codigo, f"Erro {codigo}")
