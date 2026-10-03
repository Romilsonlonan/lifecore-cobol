"""
Cosseguro — Gestão de participação entre seguradoras congêneres
GET    /api/cosseguro/participacoes
POST   /api/cosseguro/participacoes
GET    /api/cosseguro/participacoes/{cd_cosseguro}
PUT    /api/cosseguro/participacoes/{cd_cosseguro}/confirmar
PUT    /api/cosseguro/participacoes/{cd_cosseguro}/cancelar
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from typing import Optional

router = APIRouter()

_DB: dict[int, dict] = {}
_NEXT_ID = 1


class ParticipacaoCreate(BaseModel):
    nr_apolice:         str = Field(..., max_length=20)
    cd_congenere_lider: int = Field(..., description="Seguradora líder")
    cd_congenere_segui: int = Field(..., description="Seguradora seguidora")
    pct_participacao:   float = Field(..., gt=0, le=100, description="% da seguidora")
    vl_capital_cedido:  float = Field(..., gt=0)
    vl_premio_cedido:   float = Field(..., gt=0)
    dt_inicio_vigencia: str   = Field(..., pattern=r"^\d{8}$")
    dt_fim_vigencia:    str   = Field(..., pattern=r"^\d{8}$")

    @model_validator(mode="after")
    def vigencia_valida(self):
        if self.dt_fim_vigencia <= self.dt_inicio_vigencia:
            raise ValueError("dt_fim_vigencia deve ser maior que dt_inicio_vigencia.")
        return self


class ParticipacaoResponse(ParticipacaoCreate):
    cd_cosseguro:   int
    cd_status:      str   # PENDENTE / CONFIRMADO / CANCELADO
    dt_inclusao:    str
    ts_inclusao:    datetime

    class Config:
        from_attributes = True


class ConfirmacaoRequest(BaseModel):
    id_usuario:     str = Field(..., max_length=8)
    ds_observacao:  Optional[str] = None


@router.get(
    "",
    response_model=list[ParticipacaoResponse],
    summary="Lista participações de cosseguro",
)
def listar_participacoes(nr_apolice: str | None = None, cd_status: str | None = None):
    result = list(_DB.values())
    if nr_apolice:
        result = [p for p in result if p["nr_apolice"] == nr_apolice]
    if cd_status:
        result = [p for p in result if p["cd_status"] == cd_status]
    return result


@router.post(
    "",
    response_model=ParticipacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra participação de cosseguro",
)
def criar_participacao(payload: ParticipacaoCreate):
    global _NEXT_ID
    # Impede duplicado líder+seguidor para mesma apólice
    for p in _DB.values():
        if (
            p["nr_apolice"] == payload.nr_apolice
            and p["cd_congenere_segui"] == payload.cd_congenere_segui
            and p["cd_status"] != "CANCELADO"
        ):
            raise HTTPException(
                409,
                detail=f"Já existe participação ativa da seguidora {payload.cd_congenere_segui} na apólice {payload.nr_apolice}.",
            )
    participacao = {
        "cd_cosseguro": _NEXT_ID,
        **payload.model_dump(),
        "cd_status":    "PENDENTE",
        "dt_inclusao":  datetime.today().strftime("%Y%m%d"),
        "ts_inclusao":  datetime.utcnow(),
    }
    _DB[_NEXT_ID] = participacao
    _NEXT_ID += 1
    return participacao


@router.get(
    "/{cd_cosseguro}",
    response_model=ParticipacaoResponse,
    summary="Detalha participação",
)
def detalhar_participacao(cd_cosseguro: int):
    p = _DB.get(cd_cosseguro)
    if not p:
        raise HTTPException(404, detail=f"Cosseguro {cd_cosseguro} não encontrado.")
    return p


@router.put(
    "/{cd_cosseguro}/confirmar",
    response_model=ParticipacaoResponse,
    summary="Confirma participação de cosseguro",
)
def confirmar_participacao(cd_cosseguro: int, payload: ConfirmacaoRequest):
    p = _DB.get(cd_cosseguro)
    if not p:
        raise HTTPException(404, detail=f"Cosseguro {cd_cosseguro} não encontrado.")
    if p["cd_status"] != "PENDENTE":
        raise HTTPException(409, detail=f"Status {p['cd_status']} não permite confirmação.")
    p["cd_status"]      = "CONFIRMADO"
    p["id_usuario_conf"] = payload.id_usuario
    p["dt_confirmacao"] = datetime.today().strftime("%Y%m%d")
    return p


@router.put(
    "/{cd_cosseguro}/cancelar",
    response_model=ParticipacaoResponse,
    summary="Cancela participação de cosseguro",
)
def cancelar_participacao(cd_cosseguro: int, payload: ConfirmacaoRequest):
    p = _DB.get(cd_cosseguro)
    if not p:
        raise HTTPException(404, detail=f"Cosseguro {cd_cosseguro} não encontrado.")
    if p["cd_status"] == "CANCELADO":
        raise HTTPException(409, detail="Participação já cancelada.")
    p["cd_status"]      = "CANCELADO"
    p["id_usuario_canc"] = payload.id_usuario
    p["ds_observacao"]  = payload.ds_observacao
    return p
