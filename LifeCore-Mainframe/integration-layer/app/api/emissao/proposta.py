"""
Emissão — Proposta → Aceitação → Apólice
POST   /api/emissao/propostas
GET    /api/emissao/propostas
GET    /api/emissao/propostas/{nr_proposta}
POST   /api/emissao/propostas/{nr_proposta}/aceitar
POST   /api/emissao/propostas/{nr_proposta}/recusar
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.schemas.lifecore import (
    PropostaCreate,
    PropostaResponse,
    AceitePropostaRequest,
    RecusaPropostaRequest,
    StatusPropostaEnum,
    StatusApoliceEnum,
)

router = APIRouter()

# Stub em memória
_PROPOSTAS: dict[str, dict] = {}
_APOLICES: dict[str, dict] = {}
_APOLICE_SEQ = 1


def _gerar_nr_apolice() -> str:
    global _APOLICE_SEQ
    nr = f"{datetime.today().year}.APO.{_APOLICE_SEQ:06d}"
    _APOLICE_SEQ += 1
    return nr


@router.post(
    "",
    response_model=PropostaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra proposta",
)
def criar_proposta(payload: PropostaCreate):
    if payload.nr_proposta in _PROPOSTAS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposta {payload.nr_proposta} já existe.",
        )
    proposta = {
        **payload.model_dump(),
        "cd_status": StatusPropostaEnum.EM_ANALISE,
        "tp_aceite": None,
        "dt_aceite": None,
        "dt_recusa": None,
        "ds_motivo_recusa": None,
        "nr_dias_analise": 15,
        "ts_inclusao": datetime.utcnow(),
    }
    _PROPOSTAS[payload.nr_proposta] = proposta
    return proposta


@router.get("", response_model=list[PropostaResponse], summary="Lista propostas")
def listar_propostas(cd_status: StatusPropostaEnum | None = None):
    result = list(_PROPOSTAS.values())
    if cd_status:
        result = [p for p in result if p["cd_status"] == cd_status]
    return result


@router.get(
    "/{nr_proposta}", response_model=PropostaResponse, summary="Detalha proposta"
)
def detalhar_proposta(nr_proposta: str):
    p = _PROPOSTAS.get(nr_proposta)
    if not p:
        raise HTTPException(404, detail=f"Proposta {nr_proposta} não encontrada.")
    return p


@router.post(
    "/{nr_proposta}/aceitar",
    response_model=PropostaResponse,
    summary="Aceita proposta → gera apólice",
)
def aceitar_proposta(nr_proposta: str, payload: AceitePropostaRequest):
    p = _PROPOSTAS.get(nr_proposta)
    if not p:
        raise HTTPException(404, detail=f"Proposta {nr_proposta} não encontrada.")
    if p["cd_status"] not in (StatusPropostaEnum.EM_ANALISE, StatusPropostaEnum.PENDENTE_DOC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposta está em status {p['cd_status']} — não pode ser aceita.",
        )
    hoje = datetime.today().strftime("%Y%m%d")
    p["cd_status"]  = StatusPropostaEnum.ACEITA
    p["tp_aceite"]  = payload.tp_aceite
    p["dt_aceite"]  = hoje

    # Emite apólice automaticamente
    nr_apolice = _gerar_nr_apolice()
    _APOLICES[nr_apolice] = {
        "nr_apolice":       nr_apolice,
        "nr_proposta":      nr_proposta,
        "cd_empresa":       p["cd_empresa"],
        "cd_cpf_segurado":  p["cd_cpf_segurado"],
        "cd_produto":       p["cd_produto"],
        "tp_capital":       p["tp_capital"],
        "vl_capital":       p["vl_capital"],
        "vl_premio_bruto":  p.get("vl_premio_bruto"),
        "dt_emissao":       hoje,
        "dt_inicio_vigencia": hoje,
        "cd_status":        StatusApoliceEnum.ATIVA,
        "id_usuario_aceit": payload.id_usuario,
        "ts_emissao":       datetime.utcnow(),
    }
    p["nr_apolice_gerada"] = nr_apolice
    return p


@router.post(
    "/{nr_proposta}/recusar",
    response_model=PropostaResponse,
    summary="Recusa proposta",
)
def recusar_proposta(nr_proposta: str, payload: RecusaPropostaRequest):
    p = _PROPOSTAS.get(nr_proposta)
    if not p:
        raise HTTPException(404, detail=f"Proposta {nr_proposta} não encontrada.")
    if p["cd_status"] == StatusPropostaEnum.ACEITA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposta já aceita — use cancelamento de apólice.",
        )
    p["cd_status"]       = StatusPropostaEnum.RECUSADA
    p["dt_recusa"]       = datetime.today().strftime("%Y%m%d")
    p["ds_motivo_recusa"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    return p
