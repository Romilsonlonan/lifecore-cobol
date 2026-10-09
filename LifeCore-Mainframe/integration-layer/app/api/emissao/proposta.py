"""
Emissão — Proposta → Aceitação → Apólice
POST   /api/emissao/propostas
GET    /api/emissao/propostas
GET    /api/emissao/propostas/{nr_proposta}
POST   /api/emissao/propostas/{nr_proposta}/aceitar
POST   /api/emissao/propostas/{nr_proposta}/recusar

Persistência: Supabase (tabelas `propostas` e `apolices`).
Fallback in-memory quando Supabase não está configurado (dev/CI sem .env).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.schemas.lifecore import (
    AceitePropostaRequest,
    PropostaCreate,
    PropostaResponse,
    RecusaPropostaRequest,
    StatusApoliceEnum,
    StatusPropostaEnum,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Fallback in-memory (dev sem Supabase configurado) ─────────────────────────
_PROPOSTAS: dict[str, dict] = {}
_APOLICES: dict[str, dict] = {}
_APOLICE_SEQ_POR_ANO: dict[int, int] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sb_ok(table: str = "propostas") -> bool:
    """True se o Supabase está configurado e a tabela disponível."""
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


def _gerar_nr_apolice_local() -> str:
    """Sequência in-memory — usada somente quando Supabase indisponível."""
    ano = datetime.now(UTC).year
    seq = _APOLICE_SEQ_POR_ANO.get(ano, 0) + 1
    _APOLICE_SEQ_POR_ANO[ano] = seq
    return f"{ano}{seq:04d}"


def _gerar_nr_apolice_sb() -> str:
    """Lê o maior seq do Supabase e incrementa — equivalente a apolice_seq usado pelo portal."""
    from app.services.supabase_client import get_client
    ano = datetime.now(UTC).year
    sb = get_client()
    sel = sb.table("apolice_seq").select("seq").eq("ano", ano).execute()
    seq = (sel.data[0]["seq"] + 1) if sel.data else 1
    sb.table("apolice_seq").upsert({"ano": ano, "seq": seq}).execute()
    # Sincroniza fallback local
    _APOLICE_SEQ_POR_ANO[ano] = seq
    return f"{ano}{seq:04d}"


def _gerar_nr_apolice() -> str:
    try:
        return _gerar_nr_apolice_sb()
    except Exception:
        return _gerar_nr_apolice_local()


def _now_str() -> str:
    return datetime.now(UTC).isoformat()


def _hoje() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


# ── CRUD Supabase ─────────────────────────────────────────────────────────────

def _sb_criar_proposta(row: dict) -> dict:
    from app.repositories import supabase_repo as sr
    return sr.insert("propostas", row)


def _sb_atualizar_proposta(nr_proposta: str, data: dict) -> dict | None:
    from app.repositories import supabase_repo as sr
    return sr.update("propostas", {"nr_proposta": nr_proposta}, data)


def _sb_get_proposta(nr_proposta: str) -> dict | None:
    from app.repositories import supabase_repo as sr
    return sr.get_one("propostas", {"nr_proposta": nr_proposta})


def _sb_listar_propostas(cd_status: str | None = None) -> list[dict]:
    from app.repositories import supabase_repo as sr
    filters: dict = {}
    if cd_status:
        filters["cd_status"] = cd_status
    return sr.get_all("propostas", filters=filters, order="ts_inclusao", desc=True)


def _sb_criar_apolice(row: dict) -> dict:
    from app.repositories import supabase_repo as sr
    return sr.insert("apolices", row)


def _sb_get_apolice(nr_apolice: str) -> dict | None:
    from app.repositories import supabase_repo as sr
    return sr.get_one("apolices", {"nr_apolice": nr_apolice})


def _sb_atualizar_apolice(nr_apolice: str, data: dict) -> dict | None:
    from app.repositories import supabase_repo as sr
    return sr.update("apolices", {"nr_apolice": nr_apolice}, data)


# ── Funções públicas usadas por outros módulos (faturamento, config_apolice) ──

def get_apolice(nr_apolice: str) -> dict | None:
    """Retorna apólice do Supabase ou do fallback in-memory."""
    try:
        if _sb_ok("apolices"):
            row = _sb_get_apolice(nr_apolice)
            if row:
                return row
    except Exception as exc:
        logger.debug("Supabase get_apolice falhou (%s): %s", nr_apolice, exc)
    return _APOLICES.get(nr_apolice)


def set_apolice_status(nr_apolice: str, cd_status: str) -> None:
    """Atualiza status de apólice no Supabase e no fallback."""
    try:
        if _sb_ok("apolices"):
            _sb_atualizar_apolice(nr_apolice, {"cd_status": cd_status, "ts_alteracao": _now_str()})
    except Exception as exc:
        logger.warning("Supabase set_apolice_status falhou (%s): %s", nr_apolice, exc)
    if nr_apolice in _APOLICES:
        _APOLICES[nr_apolice]["cd_status"] = cd_status


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=PropostaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra proposta",
)
def criar_proposta(payload: PropostaCreate):
    # Verifica duplicidade
    if _sb_ok("propostas"):
        if _sb_get_proposta(payload.nr_proposta):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proposta {payload.nr_proposta} já existe.",
            )
    elif payload.nr_proposta in _PROPOSTAS:
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
        "ts_inclusao": _now_str(),
        "ts_alteracao": None,
        "nr_apolice_gerada": None,
    }

    try:
        if _sb_ok("propostas"):
            row = _sb_criar_proposta({k: v for k, v in proposta.items() if k != "ts_inclusao"})
            proposta.update(row)
    except Exception as exc:
        logger.warning("Supabase criar_proposta falhou — usando in-memory: %s", exc)

    _PROPOSTAS[payload.nr_proposta] = proposta
    return proposta


@router.get("", response_model=list[PropostaResponse], summary="Lista propostas")
def listar_propostas(cd_status: StatusPropostaEnum | None = None):
    try:
        if _sb_ok("propostas"):
            return _sb_listar_propostas(cd_status)
    except Exception as exc:
        logger.warning("Supabase listar_propostas falhou — usando in-memory: %s", exc)

    result = list(_PROPOSTAS.values())
    if cd_status:
        result = [p for p in result if p["cd_status"] == cd_status]
    return result


@router.get(
    "/{nr_proposta}", response_model=PropostaResponse, summary="Detalha proposta"
)
def detalhar_proposta(nr_proposta: str):
    try:
        if _sb_ok("propostas"):
            p = _sb_get_proposta(nr_proposta)
            if p:
                return p
    except Exception as exc:
        logger.debug("Supabase detalhar_proposta falhou: %s", exc)

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
    # Lê de qualquer origem
    p: dict | None = None
    use_sb = _sb_ok("propostas")
    try:
        if use_sb:
            p = _sb_get_proposta(nr_proposta)
    except Exception:
        use_sb = False
    if not p:
        p = _PROPOSTAS.get(nr_proposta)
    if not p:
        raise HTTPException(404, detail=f"Proposta {nr_proposta} não encontrada.")

    if p["cd_status"] not in (
        StatusPropostaEnum.EM_ANALISE,
        StatusPropostaEnum.PENDENTE_DOC,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposta está em status {p['cd_status']} — não pode ser aceita.",
        )

    hoje = _hoje()
    nr_apolice = _gerar_nr_apolice()

    updates = {
        "cd_status": StatusPropostaEnum.ACEITA,
        "tp_aceite": payload.tp_aceite,
        "dt_aceite": hoje,
        "nr_apolice_gerada": nr_apolice,
        "ts_alteracao": _now_str(),
    }
    p.update(updates)

    ts_emissao_now = datetime.now(UTC)
    apolice = {
        "nr_apolice": nr_apolice,
        "nr_proposta": nr_proposta,
        "cd_empresa": p.get("cd_empresa", 0),
        "cd_cpf_segurado": p.get("cd_cpf_segurado", ""),
        "cd_produto": p.get("cd_produto", "VGC"),
        "tp_capital": p.get("tp_capital", "F"),
        "vl_capital": p.get("vl_capital", 0),
        "vl_premio_bruto": p.get("vl_premio_bruto"),
        "vl_premio_liquido": p.get("vl_premio_liquido"),
        "dt_emissao": hoje,
        "dt_inicio_vigencia": hoje,
        "dt_fim_vigencia": None,
        "cd_status": StatusApoliceEnum.ATIVA,
        "id_usuario_emissao": payload.id_usuario,
        "id_usuario_aceit": payload.id_usuario,
        "ts_emissao": ts_emissao_now,          # datetime para in-memory
        "ts_emissao_sb": ts_emissao_now.isoformat(),  # string para Supabase
    }

    # Monta payload para Supabase sem campos datetime não-serializáveis
    apolice_sb = {k: v for k, v in apolice.items() if k not in ("ts_emissao", "ts_emissao_sb")}
    apolice_sb["ts_emissao"] = apolice["ts_emissao_sb"]

    try:
        if use_sb:
            _sb_atualizar_proposta(nr_proposta, {k: v for k, v in updates.items() if k != "ts_alteracao"} | {"ts_alteracao": updates["ts_alteracao"]})
            saved = _sb_criar_apolice(apolice_sb)
            apolice.update({k: v for k, v in saved.items() if k != "ts_emissao"})
    except Exception as exc:
        logger.warning("Supabase aceitar_proposta falhou — persistindo in-memory: %s", exc)

    # Remove campo auxiliar antes de guardar no in-memory
    apolice.pop("ts_emissao_sb", None)
    _PROPOSTAS[nr_proposta] = p
    _APOLICES[nr_apolice] = apolice
    return p


@router.post(
    "/{nr_proposta}/recusar",
    response_model=PropostaResponse,
    summary="Recusa proposta",
)
def recusar_proposta(nr_proposta: str, payload: RecusaPropostaRequest):
    use_sb = _sb_ok("propostas")
    p: dict | None = None
    try:
        if use_sb:
            p = _sb_get_proposta(nr_proposta)
    except Exception:
        use_sb = False
    if not p:
        p = _PROPOSTAS.get(nr_proposta)
    if not p:
        raise HTTPException(404, detail=f"Proposta {nr_proposta} não encontrada.")

    # Normaliza: Supabase retorna string "AC", in-memory pode ter o enum
    _cd = p["cd_status"]
    _cd_str = _cd.value if hasattr(_cd, "value") else str(_cd)
    if _cd_str == StatusPropostaEnum.ACEITA.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposta já aceita — use cancelamento de apólice.",
        )

    ds = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    updates = {
        "cd_status": StatusPropostaEnum.RECUSADA,
        "dt_recusa": _hoje(),
        "ds_motivo_recusa": ds,
        "ts_alteracao": _now_str(),
    }
    p.update(updates)

    try:
        if use_sb:
            _sb_atualizar_proposta(nr_proposta, updates)
    except Exception as exc:
        logger.warning("Supabase recusar_proposta falhou: %s", exc)

    _PROPOSTAS[nr_proposta] = p
    return p
