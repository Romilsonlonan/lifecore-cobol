"""
GET /api/jobs/{job_id}/status
Retorna o status atual de um job batch.

O corretor pode fazer polling neste endpoint após submeter a importação.
Ciclo típico de status: PENDENTE → EXECUTANDO → CONCLUIDO | ERRO
"""
from fastapi import APIRouter, HTTPException
from app.schemas.apolice import JobStatusResponse
from app.services.batch_connector import obter_job

router = APIRouter()


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Status do job batch",
    description=(
        "Consulte periodicamente após chamar /api/apolices/importar. "
        "Quando status = CONCLUIDO, consulte /api/apolices/resultado/{job_id}."
    ),
)
def status_job(job_id: str):
    job = obter_job(job_id.upper())
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job
