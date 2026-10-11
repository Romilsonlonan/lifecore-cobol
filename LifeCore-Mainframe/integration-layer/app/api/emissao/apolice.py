"""
Emissão — Apólice (consulta e cancelamento)
GET    /api/emissao/apolices
GET    /api/emissao/apolices/{nr_apolice}
PUT    /api/emissao/apolices/{nr_apolice}/cancelar
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.emissao.proposta import _APOLICES  # fallback in-memory compartilhado
from app.schemas.lifecore import StatusApoliceEnum

logger = logging.getLogger(__name__)

router = APIRouter()


class ApoliceResponse(BaseModel):
    nr_apolice: str
    nr_proposta: str
    cd_empresa: int
    cd_cpf_segurado: str
    cd_produto: str
    tp_capital: str
    vl_capital: float
    vl_premio_bruto: float | None
    dt_emissao: str
    dt_inicio_vigencia: str
    cd_status: StatusApoliceEnum
    id_usuario_aceit: str
    ts_emissao: datetime

    class Config:
        from_attributes = True


class CancelamentoRequest(BaseModel):
    cd_motivo: str
    ds_motivo: str
    dt_cancelamento: str | None = None
    fl_devolver_premio: str = "N"
    id_usuario: str


def _sb_ok(table: str = "apolices") -> bool:
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


@router.get("", response_model=list[ApoliceResponse], summary="Lista apólices")
def listar_apolices(
    cd_status: StatusApoliceEnum | None = None, cd_empresa: int | None = None
):
    try:
        if _sb_ok("apolices"):
            from app.repositories import supabase_repo as sr
            filters: dict = {}
            if cd_status:
                filters["cd_status"] = cd_status.value if hasattr(cd_status, "value") else cd_status
            if cd_empresa:
                filters["cd_empresa"] = cd_empresa
            rows = sr.get_all("apolices", filters=filters, order="dt_emissao", desc=True)
            if rows:
                return rows
    except Exception as exc:
        logger.warning("Supabase listar_apolices falhou — usando in-memory: %s", exc)

    result = list(_APOLICES.values())
    if cd_status:
        result = [a for a in result if a["cd_status"] == cd_status]
    if cd_empresa:
        result = [a for a in result if a["cd_empresa"] == cd_empresa]
    return result


@router.get("/{nr_apolice}", response_model=ApoliceResponse, summary="Detalha apólice")
def detalhar_apolice(nr_apolice: str):
    from app.api.emissao.config_apolice import _get_apolice
    return _get_apolice(nr_apolice)


@router.put(
    "/{nr_apolice}/cancelar",
    summary="Cancela apólice",
)
def cancelar_apolice(nr_apolice: str, payload: CancelamentoRequest):
    # Usa _get_apolice do config_apolice — tem fallback Supabase para apólices do Portal
    from app.api.emissao.config_apolice import (
        _get_apolice,
        _persistir_status_supabase,
        _registrar,
    )

    a = _get_apolice(nr_apolice)
    if a["cd_status"] == StatusApoliceEnum.CANCELADA:
        raise HTTPException(409, detail="Apólice já cancelada.")
    a["cd_status"] = StatusApoliceEnum.CANCELADA
    a["dt_cancelamento"] = payload.dt_cancelamento or datetime.today().strftime("%Y%m%d")
    a["ds_motivo_cancel"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    a["ds_motivo_cancelamento"] = a["ds_motivo_cancel"]
    a["id_usuario_cancel"] = payload.id_usuario
    _registrar(
        nr_apolice,
        "CANCELAMENTO",
        f"Apólice cancelada. Motivo: [{payload.cd_motivo}] {payload.ds_motivo}",
        payload.id_usuario,
        "AT",
        "CA",
    )
    _persistir_status_supabase(nr_apolice, a)
    return {
        "nr_apolice": nr_apolice,
        "cd_status": "CA",
        "tp_cancelamento": "TOTAL",
        "dt_cancelamento": a["dt_cancelamento"],
        "ds_motivo": a["ds_motivo_cancel"],
        "fl_devolucao_premio": payload.fl_devolver_premio,
    }
