"""
Impressão — Controle de Geração de Documentos
GET    /api/impressao/controle
POST   /api/impressao/controle
PUT    /api/impressao/controle/{cd_controle}/fechar
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.schemas.lifecore import ControleImpressaoResponse

router = APIRouter()

_DB: dict[int, dict] = {
    1: {
        "cd_controle": 1,
        "cd_empresa": 1,
        "nm_modulo": "Emissão",
        "dt_movimento_contabil": datetime.today().strftime("%Y%m%d"),
        "nr_pendentes": 12,
        "nr_gerados": 88,
        "nr_nao_gerados": 2,
        "fl_fechado": "N",
    }
}
_NEXT_ID = 2


class ControleCreate(BaseModel):
    cd_empresa:             int
    nm_modulo:              str = Field(..., max_length=30)
    dt_movimento_contabil:  str = Field(..., pattern=r"^\d{8}$")
    nr_pendentes:           int = 0
    nr_gerados:             int = 0
    nr_nao_gerados:         int = 0


@router.get(
    "",
    response_model=list[ControleImpressaoResponse],
    summary="Lista controles de impressão",
)
def listar_controles(
    cd_empresa: int | None = None,
    nm_modulo: str | None = None,
    fl_fechado: str | None = None,
):
    result = list(_DB.values())
    if cd_empresa:
        result = [c for c in result if c["cd_empresa"] == cd_empresa]
    if nm_modulo:
        result = [c for c in result if c["nm_modulo"] == nm_modulo]
    if fl_fechado:
        result = [c for c in result if c.get("fl_fechado") == fl_fechado]
    return result


@router.post(
    "",
    response_model=ControleImpressaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria controle de impressão",
)
def criar_controle(payload: ControleCreate):
    global _NEXT_ID
    # Impede duplicado por empresa+módulo+data
    for c in _DB.values():
        if (
            c["cd_empresa"] == payload.cd_empresa
            and c["nm_modulo"] == payload.nm_modulo
            and c["dt_movimento_contabil"] == payload.dt_movimento_contabil
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Controle já existe para empresa={payload.cd_empresa} módulo={payload.nm_modulo} data={payload.dt_movimento_contabil}.",
            )
    controle = {
        "cd_controle": _NEXT_ID,
        **payload.model_dump(),
        "fl_fechado": "N",
    }
    _DB[_NEXT_ID] = controle
    _NEXT_ID += 1
    return controle


@router.put(
    "/{cd_controle}/fechar",
    response_model=ControleImpressaoResponse,
    summary="Fecha período de impressão",
)
def fechar_controle(cd_controle: int, id_usuario: str):
    c = _DB.get(cd_controle)
    if not c:
        raise HTTPException(404, detail=f"Controle {cd_controle} não encontrado.")
    if c.get("fl_fechado") == "S":
        raise HTTPException(409, detail="Controle já fechado.")
    c["fl_fechado"]         = "S"
    c["dt_fechamento"]      = datetime.today().strftime("%Y%m%d")
    c["id_usuario_fech"]    = id_usuario
    return c
