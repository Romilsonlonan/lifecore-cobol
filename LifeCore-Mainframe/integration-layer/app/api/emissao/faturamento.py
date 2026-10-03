"""
Emissão — Faturamento, Endossos e Taxas IPCA

GET    /api/emissao/apolices/{nr_apolice}/faturamento
POST   /api/emissao/apolices/{nr_apolice}/faturamento
GET    /api/emissao/apolices/{nr_apolice}/faturamento/{nr_fatura}
POST   /api/emissao/apolices/{nr_apolice}/endossos
GET    /api/emissao/apolices/{nr_apolice}/endossos
GET    /api/emissao/apolices/{nr_apolice}/endossos/{nr_endosso}
PUT    /api/emissao/apolices/{nr_apolice}/endossos/{nr_endosso}/cancelar
GET    /api/emissao/taxas-ipca        ← router_ipca
POST   /api/emissao/taxas-ipca        ← router_ipca
GET    /api/emissao/taxas-ipca/{cd_competencia}  ← router_ipca

Regras de negócio:
  - Inadimplência ≤ 3 meses: segurado permanece coberto (fl_status = ATIVA).
  - Inadimplência > 3 meses: cobertura cessa sem retroatividade (SEM_COBERTURA).
  - Reativação: nova cobertura inicia na data de reativação, SEM cobrança retroativa.
  - Reajuste: prêmio corrigido pelo IPCA mensal da competência anterior.
  - Capital tipo M (múltiplo salarial): capital = salario_base × fator_mult.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Path, Query

from app.api.emissao.proposta import _APOLICES
from app.schemas.lifecore import (
    EndossoSeguradorRequest,
    EndossoResponse,
    FaturaApoliceCreate,
    FaturaApoliceResponse,
    FaturaItemSeguro,
    TaxaIPCAVigente,
    TaxaIPCAResponse,
    StatusEndossoEnum,
    StatusCoberturaEnum,
    TipoEndossoEnum,
)

router = APIRouter()
router_ipca = APIRouter()   # montado em /api/emissao/taxas-ipca

# ── Stores in-memory ──────────────────────────────────────────────────────────
# Em produção → tabelas ENDOSSO, FATURA, FATURA_ITEM, TAXA_IPCA no PostgreSQL
_ENDOSSOS: dict[str, dict] = {}          # key: nr_endosso
_FATURAS: dict[str, dict] = {}           # key: nr_fatura
_COBERTURAS: dict[str, dict] = {}        # key: "{nr_apolice}:{cpf}"
_TAXAS_IPCA: dict[str, dict] = {}        # key: cd_competencia AAAAMM

_ENDOSSO_SEQ = 1
_FATURA_SEQ = 1
_TAXA_SEQ = 1

# Seed: taxas IPCA reais 2025-2026 (IBGE)
_SEED_TAXAS = [
    ("202501", 0.16, 4.83, "20250212"),
    ("202502", 1.31, 5.06, "20250312"),
    ("202503", 0.56, 5.48, "20250410"),
    ("202504", 0.43, 5.53, "20250514"),
    ("202505", 0.43, 5.30, "20250612"),
    ("202506", 0.24, 5.35, "20250710"),
    ("202507", 0.38, 4.50, "20250813"),
]
for _comp, _mensal, _acum, _divulg in _SEED_TAXAS:
    _TAXAS_IPCA[_comp] = {
        "cd_taxa": len(_TAXAS_IPCA) + 1,
        "cd_competencia": _comp,
        "vl_taxa_ipca": _mensal,
        "vl_taxa_acumulada": _acum,
        "dt_divulgacao": _divulg,
        "ds_fonte": "IBGE/IPCA",
        "fl_vigente": _comp == "202507",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _competencia_atual() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _gerar_nr_endosso() -> str:
    global _ENDOSSO_SEQ
    nr = f"END.{datetime.now(timezone.utc).year}.{_ENDOSSO_SEQ:07d}"
    _ENDOSSO_SEQ += 1
    return nr


def _gerar_nr_fatura() -> str:
    global _FATURA_SEQ
    nr = f"FAT.{datetime.now(timezone.utc).year}.{_FATURA_SEQ:07d}"
    _FATURA_SEQ += 1
    return nr


def _taxa_mensal_vigente() -> float:
    """Retorna a taxa IPCA mensal mais recente disponível."""
    if not _TAXAS_IPCA:
        return 0.0
    latest = sorted(_TAXAS_IPCA.keys())[-1]
    return _TAXAS_IPCA[latest]["vl_taxa_ipca"]


def _calcular_capital(apolice: dict, cobertura: dict | None = None,
                      vl_capital: float | None = None,
                      vl_salario: float | None = None,
                      fator: float | None = None) -> float:
    """
    Calcula capital segurado conforme tipo:
      F = fixo           → usa vl_capital ou da apólice
      M = múltiplo sal.  → salario_base × fator_mult
      E = escalonado     → capital base cresce 5% ao ano (simulação)
      B = por faixa      → tabela simplificada SUSEP
      P = livre          → informado pelo usurado
    """
    tp = apolice.get("tp_capital", "F")
    if tp == "M":
        sal = vl_salario or apolice.get("vl_salario_base", 0) or 0
        fat = fator or apolice.get("nr_fator_mult", 1) or 1
        return round(sal * fat, 2)
    if tp == "E":
        base = vl_capital or apolice.get("vl_capital", 0)
        anos = 1  # simplificação — produção usa data de admissão
        return round(base * (1.05 ** anos), 2)
    # F, P, B → usa o valor informado ou o da apólice
    return vl_capital or apolice.get("vl_capital", 0)


def _calcular_premio(vl_capital: float, taxa_permil: float = 2.5) -> tuple[float, float]:
    """
    Calcula prêmio bruto e líquido.
    taxa_permil: taxa em ‰ do capital segurado.
    IOF: 7,38% sobre o prêmio líquido (SUSEP).
    """
    liquido = round(vl_capital * taxa_permil / 1000, 2)
    bruto = round(liquido * 1.0738, 2)
    return bruto, liquido


def _avaliar_cobertura(nr_meses_inad: int) -> StatusCoberturaEnum:
    """
    Regra SUSEP:
      0–3 meses sem pagamento → ATIVA (grace period)
      > 3 meses → SEM_COBERTURA (sem retroatividade)
    """
    if nr_meses_inad <= 3:
        return StatusCoberturaEnum.ATIVA
    return StatusCoberturaEnum.SEM_COBERTURA


def _coberturas_da_apolice(nr_apolice: str) -> list[dict]:
    """Retorna todas as coberturas ativas de uma apólice."""
    return [
        c for k, c in _COBERTURAS.items()
        if k.startswith(f"{nr_apolice}:")
        and c.get("cd_status_cobertura") not in (
            StatusCoberturaEnum.CANCELADA, StatusCoberturaEnum.SEM_COBERTURA
        )
    ]


def _get_apolice_or_404(nr_apolice: str) -> dict:
    a = _APOLICES.get(nr_apolice)
    if not a:
        raise HTTPException(404, detail=f"Apólice {nr_apolice} não encontrada.")
    return a


# ── TAXAS IPCA ────────────────────────────────────────────────────────────────

@router_ipca.get(
    "",
    response_model=list[TaxaIPCAResponse],
    summary="Lista todas as taxas IPCA cadastradas",
    tags=["Faturamento · IPCA"],
)
def listar_taxas_ipca(fl_vigente: Optional[bool] = None):
    result = list(_TAXAS_IPCA.values())
    if fl_vigente is not None:
        result = [t for t in result if t["fl_vigente"] == fl_vigente]
    return sorted(result, key=lambda t: t["cd_competencia"], reverse=True)


@router_ipca.post(
    "",
    response_model=TaxaIPCAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra taxa IPCA de uma competência",
    tags=["Faturamento · IPCA"],
)
def cadastrar_taxa_ipca(payload: TaxaIPCAVigente):
    global _TAXA_SEQ
    if payload.cd_competencia in _TAXAS_IPCA:
        raise HTTPException(409, detail=f"Taxa IPCA para {payload.cd_competencia} já cadastrada.")
    # Desmarca vigente anterior
    for t in _TAXAS_IPCA.values():
        t["fl_vigente"] = False
    taxa = {**payload.model_dump(), "cd_taxa": _TAXA_SEQ}
    taxa["fl_vigente"] = True
    _TAXA_SEQ += 1
    _TAXAS_IPCA[payload.cd_competencia] = taxa
    return taxa


@router_ipca.get(
    "/{cd_competencia}",
    response_model=TaxaIPCAResponse,
    summary="Consulta taxa IPCA de uma competência",
    tags=["Faturamento · IPCA"],
)
def consultar_taxa_ipca(cd_competencia: str = Path(..., pattern=r'^\d{6}$')):
    t = _TAXAS_IPCA.get(cd_competencia)
    if not t:
        raise HTTPException(404, detail=f"Taxa IPCA para {cd_competencia} não encontrada.")
    return t


# ── ENDOSSOS ──────────────────────────────────────────────────────────────────

@router.post(
    "/{nr_apolice}/endossos",
    response_model=EndossoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra endosso (inclusão/exclusão/alteração de segurado)",
    tags=["Faturamento · Endossos"],
)
def registrar_endosso(
    payload: EndossoSeguradorRequest,
    nr_apolice: str = Path(..., max_length=20),
):
    apolice = _get_apolice_or_404(nr_apolice)
    from app.schemas.lifecore import StatusApoliceEnum
    if apolice["cd_status"] not in (StatusApoliceEnum.ATIVA, StatusApoliceEnum.SUSPENSA):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Apólice está {apolice['cd_status']} — endosso não permitido.",
        )

    nr_endosso = _gerar_nr_endosso()
    chave_cob = f"{nr_apolice}:{payload.cd_cpf_segurado}"

    # Calcula capital e prêmio conforme tipo de endosso
    vl_cap = None
    vl_brt = None
    vl_liq = None
    if payload.tp_endosso in (TipoEndossoEnum.INCLUSAO, TipoEndossoEnum.ALTERACAO_CAP,
                               TipoEndossoEnum.REATIVACAO):
        vl_cap = _calcular_capital(
            apolice,
            vl_capital=payload.vl_capital,
            vl_salario=payload.vl_salario_base,
            fator=payload.nr_fator_mult,
        )
        # Aplica reajuste IPCA
        taxa = _taxa_mensal_vigente()
        vl_cap_ajust = round(vl_cap * (1 + taxa / 100), 2)
        vl_brt, vl_liq = _calcular_premio(vl_cap_ajust)

    # Atualiza ou cria registro de cobertura
    if payload.tp_endosso == TipoEndossoEnum.INCLUSAO:
        if chave_cob in _COBERTURAS:
            raise HTTPException(
                409,
                detail=f"Segurado {payload.cd_cpf_segurado} já possui cobertura ativa nesta apólice.",
            )
        _COBERTURAS[chave_cob] = {
            "cd_cpf_segurado":     payload.cd_cpf_segurado,
            "nm_segurado":         payload.nm_segurado,
            "nr_apolice":          nr_apolice,
            "dt_inicio_cobertura": payload.dt_inicio_vigencia,
            "dt_ultimo_pagamento": None,
            "nr_meses_inadimplente": 0,
            "cd_status_cobertura": StatusCoberturaEnum.ATIVA,
            "fl_em_carencia":      False,
            "nr_dias_carencia":    0,
            "vl_capital_base":     vl_cap or 0,
            "vl_capital_atual":    vl_cap or 0,
            "vl_reajuste_ipca":    0.0,
            "vl_salario_base":     payload.vl_salario_base,
            "nr_fator_mult":       payload.nr_fator_mult,
            "vl_premio_bruto":     vl_brt or 0,
            "vl_premio_liquido":   vl_liq or 0,
            "vl_taxa_premio":      2.5,
            "fl_revalidado":       False,
            "dt_revalidacao":      None,
            "ds_status_detalhado": "Segurado incluído via endosso.",
        }

    elif payload.tp_endosso == TipoEndossoEnum.EXCLUSAO:
        if chave_cob not in _COBERTURAS:
            raise HTTPException(404, detail=f"Segurado {payload.cd_cpf_segurado} não encontrado nesta apólice.")
        _COBERTURAS[chave_cob]["cd_status_cobertura"] = StatusCoberturaEnum.CANCELADA
        _COBERTURAS[chave_cob]["ds_status_detalhado"] = f"Excluído via endosso {nr_endosso}."

    elif payload.tp_endosso == TipoEndossoEnum.SUSPENSAO:
        if chave_cob not in _COBERTURAS:
            raise HTTPException(404, detail=f"Segurado {payload.cd_cpf_segurado} não encontrado nesta apólice.")
        _COBERTURAS[chave_cob]["cd_status_cobertura"] = StatusCoberturaEnum.SUSPENSA
        _COBERTURAS[chave_cob]["ds_status_detalhado"] = f"Suspenso via endosso {nr_endosso}."

    elif payload.tp_endosso == TipoEndossoEnum.REATIVACAO:
        if chave_cob not in _COBERTURAS:
            raise HTTPException(404, detail=f"Segurado {payload.cd_cpf_segurado} não encontrado nesta apólice.")
        cob = _COBERTURAS[chave_cob]
        cob["cd_status_cobertura"] = StatusCoberturaEnum.ATIVA
        cob["nr_meses_inadimplente"] = 0
        cob["fl_revalidado"] = True
        cob["dt_revalidacao"] = payload.dt_inicio_vigencia
        cob["vl_capital_atual"] = vl_cap or cob["vl_capital_atual"]
        cob["vl_premio_bruto"] = vl_brt or cob["vl_premio_bruto"]
        cob["vl_premio_liquido"] = vl_liq or cob["vl_premio_liquido"]
        cob["ds_status_detalhado"] = f"Reativado sem retroativo via endosso {nr_endosso}."

    elif payload.tp_endosso in (TipoEndossoEnum.ALTERACAO_CAP, TipoEndossoEnum.ALTERACAO_SAL):
        if chave_cob not in _COBERTURAS:
            raise HTTPException(404, detail=f"Segurado {payload.cd_cpf_segurado} não encontrado nesta apólice.")
        cob = _COBERTURAS[chave_cob]
        if vl_cap:
            cob["vl_capital_atual"] = vl_cap
            cob["vl_premio_bruto"] = vl_brt
            cob["vl_premio_liquido"] = vl_liq
        if payload.vl_salario_base:
            cob["vl_salario_base"] = payload.vl_salario_base
        if payload.nr_fator_mult:
            cob["nr_fator_mult"] = payload.nr_fator_mult
        cob["ds_status_detalhado"] = f"Capital/salário alterado via endosso {nr_endosso}."

    endosso = {
        **payload.model_dump(),
        "nr_endosso":           nr_endosso,
        "nr_apolice":           nr_apolice,
        "cd_status":            StatusEndossoEnum.PROCESSADO,
        "vl_capital_calculado": vl_cap,
        "vl_premio_calculado":  vl_brt,
        "ts_inclusao":          _now(),
    }
    _ENDOSSOS[nr_endosso] = endosso
    return endosso


@router.get(
    "/{nr_apolice}/endossos",
    response_model=list[EndossoResponse],
    summary="Lista endossos de uma apólice",
    tags=["Faturamento · Endossos"],
)
def listar_endossos(
    nr_apolice: str = Path(..., max_length=20),
    tp_endosso: Optional[TipoEndossoEnum] = None,
):
    _get_apolice_or_404(nr_apolice)
    result = [e for e in _ENDOSSOS.values() if e["nr_apolice"] == nr_apolice]
    if tp_endosso:
        result = [e for e in result if e["tp_endosso"] == tp_endosso]
    return sorted(result, key=lambda e: e["ts_inclusao"], reverse=True)


@router.get(
    "/{nr_apolice}/endossos/{nr_endosso}",
    response_model=EndossoResponse,
    summary="Detalha endosso",
    tags=["Faturamento · Endossos"],
)
def detalhar_endosso(
    nr_apolice: str = Path(..., max_length=20),
    nr_endosso: str = Path(...),
):
    _get_apolice_or_404(nr_apolice)
    e = _ENDOSSOS.get(nr_endosso)
    if not e or e["nr_apolice"] != nr_apolice:
        raise HTTPException(404, detail=f"Endosso {nr_endosso} não encontrado.")
    return e


@router.put(
    "/{nr_apolice}/endossos/{nr_endosso}/cancelar",
    response_model=EndossoResponse,
    summary="Cancela endosso pendente",
    tags=["Faturamento · Endossos"],
)
def cancelar_endosso(nr_apolice: str, nr_endosso: str, id_usuario: str):
    _get_apolice_or_404(nr_apolice)
    e = _ENDOSSOS.get(nr_endosso)
    if not e or e["nr_apolice"] != nr_apolice:
        raise HTTPException(404, detail=f"Endosso {nr_endosso} não encontrado.")
    if e["cd_status"] != StatusEndossoEnum.PENDENTE:
        raise HTTPException(409, detail="Só endossos PENDENTE podem ser cancelados.")
    e["cd_status"] = StatusEndossoEnum.CANCELADO
    return e


# ── FATURAMENTO ───────────────────────────────────────────────────────────────

@router.get(
    "/{nr_apolice}/faturamento",
    response_model=list[FaturaApoliceResponse],
    summary="Lista faturas de uma apólice",
    tags=["Faturamento · Faturas"],
)
def listar_faturas(
    nr_apolice: str = Path(..., max_length=20),
    cd_competencia: Optional[str] = Query(None, pattern=r'^\d{6}$'),
    cd_status: Optional[str] = None,
):
    _get_apolice_or_404(nr_apolice)
    result = [f for f in _FATURAS.values() if f["nr_apolice"] == nr_apolice]
    if cd_competencia:
        result = [f for f in result if f["cd_competencia"] == cd_competencia]
    if cd_status:
        result = [f for f in result if f["cd_status"] == cd_status]
    return sorted(result, key=lambda f: f["cd_competencia"], reverse=True)


@router.post(
    "/{nr_apolice}/faturamento",
    response_model=FaturaApoliceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gera fatura de uma apólice para a competência informada",
    tags=["Faturamento · Faturas"],
)
def gerar_fatura(
    payload: FaturaApoliceCreate,
    nr_apolice: str = Path(..., max_length=20),
):
    apolice = _get_apolice_or_404(nr_apolice)
    # Impede duplicidade
    dupe = [
        f for f in _FATURAS.values()
        if f["nr_apolice"] == nr_apolice and f["cd_competencia"] == payload.cd_competencia
    ]
    if dupe:
        raise HTTPException(
            409,
            detail=f"Fatura para competência {payload.cd_competencia} já existe: {dupe[0]['nr_fatura']}.",
        )

    taxa_mensal = _taxa_mensal_vigente()
    itens: list[dict] = []
    vl_total_bruto = 0.0
    vl_total_liq = 0.0
    vl_total_ipca = 0.0

    coberturas = _coberturas_da_apolice(nr_apolice)

    # Se não há coberturas ainda, cria uma a partir da própria apólice (backward compat)
    if not coberturas:
        vl_cap_base = apolice.get("vl_capital", 0) or 0
        vl_cap_ajust = round(vl_cap_base * (1 + taxa_mensal / 100), 2)
        vl_ipca = round(vl_cap_ajust - vl_cap_base, 2)
        vl_brt, vl_liq = _calcular_premio(vl_cap_ajust)
        itens.append({
            "cd_cpf_segurado":     apolice.get("cd_cpf_segurado", "00000000000"),
            "nm_segurado":         "SEGURADO PRINCIPAL",
            "vl_capital_coberto":  vl_cap_ajust,
            "vl_premio_bruto":     vl_brt,
            "vl_premio_liquido":   vl_liq,
            "vl_reajuste_ipca":    vl_ipca,
            "cd_status_cobertura": StatusCoberturaEnum.ATIVA,
            "dt_inicio_cobertura": apolice.get("dt_inicio_vigencia", _hoje()),
            "dt_fim_cobertura":    None,
            "fl_revalidado":       False,
            "ds_observacao":       "Capital gerado diretamente da apólice.",
        })
        vl_total_bruto += vl_brt
        vl_total_liq += vl_liq
        vl_total_ipca += vl_ipca
    else:
        for cob in coberturas:
            vl_cap_base = cob["vl_capital_base"]
            vl_cap_atual = cob["vl_capital_atual"]
            vl_cap_ajust = round(vl_cap_atual * (1 + taxa_mensal / 100), 2)
            vl_ipca = round(vl_cap_ajust - vl_cap_atual, 2)

            # Atualiza capital com IPCA
            cob["vl_capital_atual"] = vl_cap_ajust
            cob["vl_reajuste_ipca"] = round(cob.get("vl_reajuste_ipca", 0) + vl_ipca, 2)

            vl_brt, vl_liq = _calcular_premio(vl_cap_ajust)
            cob["vl_premio_bruto"] = vl_brt
            cob["vl_premio_liquido"] = vl_liq
            cob["dt_ultimo_pagamento"] = _hoje()

            itens.append({
                "cd_cpf_segurado":     cob["cd_cpf_segurado"],
                "nm_segurado":         cob["nm_segurado"],
                "vl_capital_coberto":  vl_cap_ajust,
                "vl_premio_bruto":     vl_brt,
                "vl_premio_liquido":   vl_liq,
                "vl_reajuste_ipca":    vl_ipca,
                "cd_status_cobertura": cob["cd_status_cobertura"],
                "dt_inicio_cobertura": cob["dt_inicio_cobertura"],
                "dt_fim_cobertura":    None,
                "fl_revalidado":       cob.get("fl_revalidado", False),
                "ds_observacao":       cob.get("ds_status_detalhado"),
            })
            vl_total_bruto += vl_brt
            vl_total_liq += vl_liq
            vl_total_ipca += vl_ipca

    nr_fatura = _gerar_nr_fatura()
    fatura = {
        "nr_fatura":       nr_fatura,
        "nr_apolice":      nr_apolice,
        "cd_empresa":      apolice.get("cd_empresa", 0),
        "cd_competencia":  payload.cd_competencia,
        "dt_emissao":      _hoje(),
        "dt_vencimento":   payload.dt_vencimento,
        "forma_cobranca":  payload.forma_cobranca,
        "vl_total_bruto":  round(vl_total_bruto, 2),
        "vl_total_liquido": round(vl_total_liq, 2),
        "vl_reajuste_ipca": round(vl_total_ipca, 2),
        "nr_segurados":    len(itens),
        "itens":           itens,
        "cd_status":       "EM_ABERTO",
        "ts_geracao":      _now(),
    }
    _FATURAS[nr_fatura] = fatura
    return fatura


@router.get(
    "/{nr_apolice}/faturamento/{nr_fatura}",
    response_model=FaturaApoliceResponse,
    summary="Detalha fatura",
    tags=["Faturamento · Faturas"],
)
def detalhar_fatura(
    nr_apolice: str = Path(..., max_length=20),
    nr_fatura: str = Path(...),
):
    _get_apolice_or_404(nr_apolice)
    f = _FATURAS.get(nr_fatura)
    if not f or f["nr_apolice"] != nr_apolice:
        raise HTTPException(404, detail=f"Fatura {nr_fatura} não encontrada.")
    return f
