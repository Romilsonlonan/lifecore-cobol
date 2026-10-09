"""
Sinistro — Abertura, Análise, Pagamento e Encerramento
POST   /api/sinistro
GET    /api/sinistro
GET    /api/sinistro/{nr_sinistro}
PUT    /api/sinistro/{nr_sinistro}/analisar
PUT    /api/sinistro/{nr_sinistro}/pagar
PUT    /api/sinistro/{nr_sinistro}/encerrar

Persistência: Supabase (tabela `sinistros`).
Fallback in-memory quando Supabase não configurado.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.lifecore import (
    SinistroCreate,
    SinistroResponse,
    StatusSinistroEnum,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_DB: dict[str, dict] = {}  # fallback in-memory


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sb_ok(table: str = "sinistros") -> bool:
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


def _now_str() -> str:
    return datetime.now(UTC).isoformat()


def _hoje() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _get_sinistro(nr_sinistro: str) -> dict | None:
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            row = sr.get_one("sinistros", {"nr_sinistro": nr_sinistro})
            if row:
                return row
    except Exception as exc:
        logger.debug("Supabase get_sinistro falhou: %s", exc)
    return _DB.get(nr_sinistro)


def _save_sinistro(s: dict) -> dict:
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            row = sr.upsert("sinistros", {k: v for k, v in s.items() if k not in ("ts_inclusao",)})
            s.update(row)
    except Exception as exc:
        logger.warning("Supabase save_sinistro falhou: %s", exc)
    _DB[s["nr_sinistro"]] = s
    return s


def _update_sinistro(nr_sinistro: str, data: dict) -> None:
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            sr.update("sinistros", {"nr_sinistro": nr_sinistro}, data | {"ts_alteracao": _now_str()})
    except Exception as exc:
        logger.warning("Supabase update_sinistro falhou: %s", exc)
    if nr_sinistro in _DB:
        _DB[nr_sinistro].update(data)


# ── Schemas extras ────────────────────────────────────────────────────────────

class AnaliseRequest(BaseModel):
    parecer: str = Field(..., pattern=r"^(FAVORAVEL|DESFAVORAVEL|PENDENTE)$")
    ds_parecer: str = Field(..., max_length=300)
    vl_indenizacao: float | None = None
    id_usuario: str = Field(..., max_length=20)


class PagamentoSinistroRequest(BaseModel):
    vl_pago: float = Field(..., gt=0)
    dt_pagamento: str = Field(..., pattern=r"^\d{8}$")
    nr_doc_banco: str = Field(..., max_length=20)
    id_usuario: str = Field(..., max_length=20)


class EncerramentoRequest(BaseModel):
    ds_motivo: str = Field(..., max_length=200)
    id_usuario: str = Field(..., max_length=20)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SinistroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abre sinistro",
)
def abrir_sinistro(payload: SinistroCreate):
    if _get_sinistro(payload.nr_sinistro):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sinistro {payload.nr_sinistro} já existe.",
        )
    sinistro = {
        **payload.model_dump(),
        "cd_status": StatusSinistroEnum.ABERTO,
        "vl_pago": 0.0,
        "dt_encerramento": None,
        "ts_inclusao": _now_str(),
        "ts_alteracao": None,
    }
    return _save_sinistro(sinistro)


@router.get("", response_model=list[SinistroResponse], summary="Lista sinistros")
def listar_sinistros(
    cd_status: StatusSinistroEnum | None = None,
    cd_empresa: int | None = None,
):
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            filters: dict = {}
            if cd_status:
                filters["cd_status"] = cd_status
            if cd_empresa:
                filters["cd_empresa"] = cd_empresa
            return sr.get_all("sinistros", filters=filters, order="ts_inclusao", desc=True)
    except Exception as exc:
        logger.warning("Supabase listar_sinistros falhou: %s", exc)

    result = list(_DB.values())
    if cd_status:
        result = [s for s in result if s["cd_status"] == cd_status]
    if cd_empresa:
        result = [s for s in result if s["cd_empresa"] == cd_empresa]
    return result


@router.get(
    "/{nr_sinistro}", response_model=SinistroResponse, summary="Detalha sinistro"
)
def detalhar_sinistro(nr_sinistro: str):
    s = _get_sinistro(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    return s


@router.put(
    "/{nr_sinistro}/analisar",
    response_model=SinistroResponse,
    summary="Registra análise / parecer",
)
def analisar_sinistro(nr_sinistro: str, payload: AnaliseRequest):
    s = _get_sinistro(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] not in (StatusSinistroEnum.ABERTO, StatusSinistroEnum.EM_ANALISE):
        raise HTTPException(409, detail=f"Status {s['cd_status']} não permite análise.")

    upd = {
        "cd_status": StatusSinistroEnum.EM_ANALISE,
        "parecer": payload.parecer,
        "ds_parecer": payload.ds_parecer,
    }
    if payload.vl_indenizacao is not None:
        upd["vl_indenizacao"] = payload.vl_indenizacao
    _update_sinistro(nr_sinistro, upd)
    s.update(upd)
    return s


@router.put(
    "/{nr_sinistro}/pagar",
    response_model=SinistroResponse,
    summary="Registra pagamento de sinistro",
)
def pagar_sinistro(nr_sinistro: str, payload: PagamentoSinistroRequest):
    s = _get_sinistro(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] == StatusSinistroEnum.ENCERRADO:
        raise HTTPException(409, detail="Sinistro já encerrado.")

    novo_pago = float(s.get("vl_pago") or 0) + payload.vl_pago
    upd = {
        "vl_pago": novo_pago,
        "dt_pagamento": payload.dt_pagamento,
        "nr_doc_banco": payload.nr_doc_banco,
        "cd_status": StatusSinistroEnum.PAGO,
    }
    _update_sinistro(nr_sinistro, upd)
    s.update(upd)
    return s


@router.put(
    "/{nr_sinistro}/encerrar",
    response_model=SinistroResponse,
    summary="Encerra sinistro",
)
def encerrar_sinistro(nr_sinistro: str, payload: EncerramentoRequest):
    s = _get_sinistro(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] == StatusSinistroEnum.ENCERRADO:
        raise HTTPException(409, detail="Sinistro já encerrado.")

    upd = {
        "cd_status": StatusSinistroEnum.ENCERRADO,
        "dt_encerramento": _hoje(),
        "ds_encerramento": payload.ds_motivo,
    }
    _update_sinistro(nr_sinistro, upd)
    s.update(upd)
    return s
