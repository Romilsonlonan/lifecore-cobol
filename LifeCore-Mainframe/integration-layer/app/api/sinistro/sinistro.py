"""
Sinistro — Abertura, Análise, Pagamento e Encerramento
POST   /api/sinistro
GET    /api/sinistro
GET    /api/sinistro/{nr_sinistro}
PUT    /api/sinistro/{nr_sinistro}/analisar
PUT    /api/sinistro/{nr_sinistro}/pagar
PUT    /api/sinistro/{nr_sinistro}/encerrar
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.schemas.lifecore import (
    SinistroCreate,
    SinistroResponse,
    StatusSinistroEnum,
)

router = APIRouter()

_DB: dict[str, dict] = {}


class AnaliseRequest(BaseModel):
    parecer:        str = Field(..., pattern=r"^(FAVORAVEL|DESFAVORAVEL|PENDENTE)$")
    ds_parecer:     str = Field(..., max_length=300)
    vl_indenizacao: Optional[float] = None
    id_usuario:     str = Field(..., max_length=20)


class PagamentoSinistroRequest(BaseModel):
    vl_pago:        float = Field(..., gt=0)
    dt_pagamento:   str   = Field(..., pattern=r"^\d{8}$")
    nr_doc_banco:   str   = Field(..., max_length=20)
    id_usuario:     str   = Field(..., max_length=20)


class EncerramentoRequest(BaseModel):
    ds_motivo:  str = Field(..., max_length=200)
    id_usuario: str = Field(..., max_length=20)


@router.post(
    "",
    response_model=SinistroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abre sinistro",
)
def abrir_sinistro(payload: SinistroCreate):
    if payload.nr_sinistro in _DB:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sinistro {payload.nr_sinistro} já existe.",
        )
    sinistro = {
        **payload.model_dump(),
        "cd_status":        StatusSinistroEnum.ABERTO,
        "vl_pago":          0.0,
        "dt_encerramento":  None,
        "ts_inclusao":      datetime.utcnow(),
    }
    _DB[payload.nr_sinistro] = sinistro
    return sinistro


@router.get("", response_model=list[SinistroResponse], summary="Lista sinistros")
def listar_sinistros(
    cd_status: StatusSinistroEnum | None = None,
    cd_empresa: int | None = None,
):
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
    s = _DB.get(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    return s


@router.put(
    "/{nr_sinistro}/analisar",
    response_model=SinistroResponse,
    summary="Registra análise / parecer",
)
def analisar_sinistro(nr_sinistro: str, payload: AnaliseRequest):
    s = _DB.get(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] not in (StatusSinistroEnum.ABERTO, StatusSinistroEnum.EM_ANALISE):
        raise HTTPException(409, detail=f"Status {s['cd_status']} não permite análise.")
    s["cd_status"] = StatusSinistroEnum.EM_ANALISE
    s["parecer"]   = payload.parecer
    s["ds_parecer"] = payload.ds_parecer
    if payload.vl_indenizacao is not None:
        s["vl_indenizacao"] = payload.vl_indenizacao
    return s


@router.put(
    "/{nr_sinistro}/pagar",
    response_model=SinistroResponse,
    summary="Registra pagamento de sinistro",
)
def pagar_sinistro(nr_sinistro: str, payload: PagamentoSinistroRequest):
    s = _DB.get(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] == StatusSinistroEnum.ENCERRADO:
        raise HTTPException(409, detail="Sinistro já encerrado.")
    s["vl_pago"]      += payload.vl_pago
    s["dt_pagamento"]  = payload.dt_pagamento
    s["nr_doc_banco"]  = payload.nr_doc_banco
    s["cd_status"]     = StatusSinistroEnum.PAGO
    return s


@router.put(
    "/{nr_sinistro}/encerrar",
    response_model=SinistroResponse,
    summary="Encerra sinistro",
)
def encerrar_sinistro(nr_sinistro: str, payload: EncerramentoRequest):
    s = _DB.get(nr_sinistro)
    if not s:
        raise HTTPException(404, detail=f"Sinistro {nr_sinistro} não encontrado.")
    if s["cd_status"] == StatusSinistroEnum.ENCERRADO:
        raise HTTPException(409, detail="Sinistro já encerrado.")
    s["cd_status"]      = StatusSinistroEnum.ENCERRADO
    s["dt_encerramento"] = datetime.today().strftime("%Y%m%d")
    s["ds_encerramento"] = payload.ds_motivo
    return s
