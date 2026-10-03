"""
Emissão — Consulta Detalhada de Apólice

GET  /api/emissao/apolices/{nr_apolice}/detalhes
     Retorna visão consolidada: identificação, config, coberturas por segurado,
     totalizadores, taxa IPCA vigente e últimas faturas.

GET  /api/emissao/apolices/{nr_apolice}/coberturas
     Lista coberturas individuais com cálculo de inadimplência em tempo real.

GET  /api/emissao/apolices/{nr_apolice}/coberturas/{cpf}
     Detalha cobertura de um segurado específico.

POST /api/emissao/apolices/{nr_apolice}/coberturas/{cpf}/revalidar
     Aplica regra de revalidação:
       ≤ 3 meses sem pagamento → volta ATIVA (grace period)
       > 3 meses sem pagamento → ATIVA com nova vigência, SEM retroativo

POST /api/emissao/apolices/{nr_apolice}/coberturas/{cpf}/registrar-inadimplencia
     Avança o contador de meses inadimplentes e recalcula status automaticamente.

Regras de negócio:
  • Grace period SUSEP: 3 meses sem pagamento → cobertura mantida (ATIVA).
  • Após 3 meses: status muda para SEM_COBERTURA sem cobrança retroativa.
  • Revalidação: cobertura reinicia na data informada. Período sem cobertura
    NÃO gera cobrança retroativa (conforme regulação).
  • IPCA: capital e prêmio são corrigidos mensalmente pela taxa vigente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status

from app.api.emissao.proposta import _APOLICES
from app.api.emissao.faturamento import _COBERTURAS, _FATURAS, _TAXAS_IPCA
from app.schemas.lifecore import (
    CoberturaSeguro,
    DetalheApoliceCompleto,
    RevalidacaoRequest,
    RevalidacaoResponse,
    StatusCoberturaEnum,
    StatusApoliceEnum,
    PeriodicidadeEnum,
    FormaCobrancaEnum,
    TaxaIPCAResponse,
)

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

_PRODUTO_NOME = {"VGC": "Vida em Grupo Coletivo", "GLB": "Global Life Balance"}
_CAPITAL_NOME = {
    "F": "Capital Fixo",
    "M": "Múltiplo Salarial",
    "E": "Escalonado",
    "B": "Por Faixa Etária",
    "P": "Livre (Parametrizável)",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _get_apolice_or_404(nr_apolice: str) -> dict:
    a = _APOLICES.get(nr_apolice)
    if not a:
        raise HTTPException(404, detail=f"Apólice {nr_apolice} não encontrada.")
    return a


def _get_cobertura_or_404(nr_apolice: str, cpf: str) -> dict:
    chave = f"{nr_apolice}:{cpf}"
    c = _COBERTURAS.get(chave)
    if not c:
        raise HTTPException(
            404,
            detail=f"Segurado CPF {cpf} não possui cobertura na apólice {nr_apolice}.",
        )
    return c


def _taxa_ipca_vigente() -> dict | None:
    if not _TAXAS_IPCA:
        return None
    comp = sorted(_TAXAS_IPCA.keys())[-1]
    return _TAXAS_IPCA[comp]


def _status_detalhado(nr_meses: int, status: StatusCoberturaEnum) -> str:
    if status == StatusCoberturaEnum.SEM_COBERTURA:
        return (
            f"Segurado com {nr_meses} meses sem pagamento — cobertura cessada. "
            "Reativação sem cobrança retroativa disponível."
        )
    if status == StatusCoberturaEnum.ATIVA and nr_meses > 0:
        restantes = 3 - nr_meses
        return (
            f"Em grace period: {nr_meses}/3 meses sem pagamento. "
            f"{restantes} mês(es) até perda de cobertura."
        )
    if status == StatusCoberturaEnum.SUSPENSA:
        return "Cobertura suspensa por solicitação. Endosso de reativação necessário."
    if status == StatusCoberturaEnum.CANCELADA:
        return "Segurado excluído da apólice."
    return "Cobertura ativa e regular."


def _build_cobertura_schema(cob: dict) -> CoberturaSeguro:
    nr_m = cob.get("nr_meses_inadimplente", 0)
    st = cob.get("cd_status_cobertura", StatusCoberturaEnum.ATIVA)
    return CoberturaSeguro(
        cd_cpf_segurado=cob["cd_cpf_segurado"],
        nm_segurado=cob["nm_segurado"],
        dt_nascimento=cob.get("dt_nascimento"),
        dt_admissao=cob.get("dt_admissao"),
        dt_inicio_cobertura=cob["dt_inicio_cobertura"],
        dt_ultimo_pagamento=cob.get("dt_ultimo_pagamento"),
        nr_meses_inadimplente=nr_m,
        cd_status_cobertura=st,
        fl_em_carencia=cob.get("fl_em_carencia", False),
        nr_dias_carencia=cob.get("nr_dias_carencia", 0),
        vl_capital_base=cob.get("vl_capital_base", 0),
        vl_capital_atual=cob.get("vl_capital_atual", 0),
        vl_reajuste_ipca=cob.get("vl_reajuste_ipca", 0),
        vl_salario_base=cob.get("vl_salario_base"),
        nr_fator_mult=cob.get("nr_fator_mult"),
        vl_premio_bruto=cob.get("vl_premio_bruto", 0),
        vl_premio_liquido=cob.get("vl_premio_liquido", 0),
        vl_taxa_premio=cob.get("vl_taxa_premio", 2.5),
        fl_revalidado=cob.get("fl_revalidado", False),
        dt_revalidacao=cob.get("dt_revalidacao"),
        ds_status_detalhado=_status_detalhado(nr_m, st),
    )


# ── CONSULTA DETALHADA ────────────────────────────────────────────────────────

@router.get(
    "/{nr_apolice}/detalhes",
    response_model=DetalheApoliceCompleto,
    summary="Consulta detalhada da apólice com coberturas, taxas e faturas",
    tags=["Consulta Apólice"],
)
def detalhe_completo(nr_apolice: str = Path(..., max_length=20)):
    apolice = _get_apolice_or_404(nr_apolice)

    coberturas_raw = [
        c for k, c in _COBERTURAS.items()
        if k.startswith(f"{nr_apolice}:")
    ]
    coberturas_schema = [_build_cobertura_schema(c) for c in coberturas_raw]

    ativos = [
        c for c in coberturas_raw
        if c.get("cd_status_cobertura") == StatusCoberturaEnum.ATIVA
    ]
    sem_cob = [
        c for c in coberturas_raw
        if c.get("cd_status_cobertura") == StatusCoberturaEnum.SEM_COBERTURA
    ]

    vl_folha = sum(c.get("vl_capital_atual", 0) for c in ativos)
    vl_ipca_acum = sum(c.get("vl_reajuste_ipca", 0) for c in coberturas_raw)

    # Últimas 6 faturas (resumo)
    faturas_resumo = sorted(
        [
            {
                "nr_fatura": f["nr_fatura"],
                "cd_competencia": f["cd_competencia"],
                "dt_vencimento": f["dt_vencimento"],
                "vl_total_bruto": f["vl_total_bruto"],
                "cd_status": f["cd_status"],
                "nr_segurados": f["nr_segurados"],
            }
            for f in _FATURAS.values()
            if f["nr_apolice"] == nr_apolice
        ],
        key=lambda x: x["cd_competencia"],
        reverse=True,
    )[:6]

    taxa = _taxa_ipca_vigente()
    taxa_schema: TaxaIPCAResponse | None = None
    if taxa:
        taxa_schema = TaxaIPCAResponse(**taxa)

    # Config faturamento (vem do store config_apolice se existir)
    try:
        from app.api.emissao.config_apolice import _CONFIGS_FATURAMENTO
        conf = _CONFIGS_FATURAMENTO.get(nr_apolice, {})
    except ImportError:
        conf = {}

    return DetalheApoliceCompleto(
        nr_apolice=nr_apolice,
        nr_proposta=apolice.get("nr_proposta", ""),
        cd_empresa=apolice.get("cd_empresa", 0),
        nm_empresa=None,  # join com cadastro de empresa em produção
        cd_produto=apolice.get("cd_produto", ""),
        nm_produto=_PRODUTO_NOME.get(apolice.get("cd_produto", ""), ""),
        cd_status=apolice.get("cd_status", StatusApoliceEnum.ATIVA),
        dt_emissao=apolice.get("dt_emissao", ""),
        dt_inicio_vigencia=apolice.get("dt_inicio_vigencia", ""),
        dt_fim_vigencia=apolice.get("dt_fim_vigencia"),
        dt_cancelamento=apolice.get("dt_cancelamento"),
        ds_motivo_cancel=apolice.get("ds_motivo_cancel"),
        tp_capital=apolice.get("tp_capital", "F"),
        vl_capital_base=apolice.get("vl_capital", 0),
        vl_capital_atual=vl_folha or apolice.get("vl_capital", 0),
        vl_premio_bruto=apolice.get("vl_premio_bruto"),
        vl_premio_liquido=apolice.get("vl_premio_liquido"),
        periodicidade=conf.get("periodicidade"),
        forma_cobranca=conf.get("forma_cobranca"),
        dia_vencimento=conf.get("dia_vencimento"),
        nr_segurados_ativos=len(ativos),
        nr_segurados_sem_cobertura=len(sem_cob),
        vl_folha_total=round(vl_folha, 2),
        vl_reajuste_ipca_acum=round(vl_ipca_acum, 2),
        taxa_ipca_vigente=taxa_schema,
        coberturas=coberturas_schema,
        ultimas_faturas=faturas_resumo,
        ts_consulta=_now(),
    )


# ── COBERTURAS ────────────────────────────────────────────────────────────────

@router.get(
    "/{nr_apolice}/coberturas",
    response_model=list[CoberturaSeguro],
    summary="Lista coberturas de todos os segurados da apólice",
    tags=["Consulta Apólice · Coberturas"],
)
def listar_coberturas(
    nr_apolice: str = Path(..., max_length=20),
    cd_status: Optional[StatusCoberturaEnum] = None,
):
    _get_apolice_or_404(nr_apolice)
    coberturas = [
        c for k, c in _COBERTURAS.items()
        if k.startswith(f"{nr_apolice}:")
    ]
    if cd_status:
        coberturas = [
            c for c in coberturas
            if c.get("cd_status_cobertura") == cd_status
        ]
    return [_build_cobertura_schema(c) for c in coberturas]


@router.get(
    "/{nr_apolice}/coberturas/{cpf}",
    response_model=CoberturaSeguro,
    summary="Detalha cobertura de um segurado",
    tags=["Consulta Apólice · Coberturas"],
)
def detalhar_cobertura(
    nr_apolice: str = Path(..., max_length=20),
    cpf: str = Path(..., min_length=11, max_length=11),
):
    _get_apolice_or_404(nr_apolice)
    cob = _get_cobertura_or_404(nr_apolice, cpf)
    return _build_cobertura_schema(cob)


# ── INADIMPLÊNCIA ─────────────────────────────────────────────────────────────

@router.post(
    "/{nr_apolice}/coberturas/{cpf}/registrar-inadimplencia",
    response_model=CoberturaSeguro,
    summary="Avança contador de inadimplência e recalcula status de cobertura",
    tags=["Consulta Apólice · Coberturas"],
)
def registrar_inadimplencia(
    nr_apolice: str = Path(..., max_length=20),
    cpf: str = Path(..., min_length=11, max_length=11),
    id_usuario: str = "SISTEMA",
):
    """
    Incrementa nr_meses_inadimplente em +1.
    Aplica a regra SUSEP:
      ≤ 3 meses → status ATIVA (grace period mantido)
      > 3 meses → status SEM_COBERTURA (sem retroativo)
    """
    _get_apolice_or_404(nr_apolice)
    cob = _get_cobertura_or_404(nr_apolice, cpf)

    if cob["cd_status_cobertura"] in (
        StatusCoberturaEnum.CANCELADA,
        StatusCoberturaEnum.SEM_COBERTURA,
    ):
        raise HTTPException(
            409,
            detail=f"Segurado já está em status {cob['cd_status_cobertura']} — sem alteração.",
        )

    cob["nr_meses_inadimplente"] = cob.get("nr_meses_inadimplente", 0) + 1
    nr_m = cob["nr_meses_inadimplente"]

    if nr_m <= 3:
        cob["cd_status_cobertura"] = StatusCoberturaEnum.ATIVA
        cob["ds_status_detalhado"] = (
            f"Grace period: {nr_m}/3 meses sem pagamento. Cobertura mantida."
        )
    else:
        cob["cd_status_cobertura"] = StatusCoberturaEnum.SEM_COBERTURA
        cob["ds_status_detalhado"] = (
            f"Cobertura cessada após {nr_m} meses sem pagamento. "
            "Reativação disponível sem retroativo."
        )

    return _build_cobertura_schema(cob)


# ── REVALIDAÇÃO ───────────────────────────────────────────────────────────────

@router.post(
    "/{nr_apolice}/coberturas/{cpf}/revalidar",
    response_model=RevalidacaoResponse,
    status_code=status.HTTP_200_OK,
    summary="Revalida cobertura de segurado inadimplente (sem retroativo)",
    tags=["Consulta Apólice · Coberturas"],
)
def revalidar_cobertura(
    payload: RevalidacaoRequest,
    nr_apolice: str = Path(..., max_length=20),
    cpf: str = Path(..., min_length=11, max_length=11),
):
    """
    Regras de revalidação SUSEP:

    1. Grace period (≤ 3 meses):
       - O segurado já está coberto → revalidação apenas documenta e zera o contador.
       - Não há cobrança retroativa.

    2. Sem cobertura (> 3 meses):
       - A nova cobertura começa em dt_reativacao.
       - O período sem cobertura NÃO gera cobrança retroativa.
       - fl_cobrar_retroativo é sempre ignorado / mantido False.
    """
    if payload.cd_cpf_segurado != cpf:
        raise HTTPException(
            400,
            detail="CPF do payload não confere com o CPF do path.",
        )
    _get_apolice_or_404(nr_apolice)
    cob = _get_cobertura_or_404(nr_apolice, cpf)

    status_anterior = cob["cd_status_cobertura"]
    nr_meses = cob.get("nr_meses_inadimplente", 0)

    if status_anterior == StatusCoberturaEnum.CANCELADA:
        raise HTTPException(
            409,
            detail="Segurado cancelado não pode ser revalidado. Emita um endosso de inclusão.",
        )

    # Calcula prêmio devido apenas se grace period (≤ 3 meses, cobertura mantida)
    vl_devido = 0.0
    mensagem = ""

    if nr_meses <= 3:
        # Grace period — cobertura nunca cessou; apenas normaliza
        mensagem = (
            f"Segurado em grace period ({nr_meses}/3 meses). "
            "Cobertura já estava mantida. Contador de inadimplência zerado."
        )
        vl_devido = 0.0
    else:
        # Cobertura cessada — reativa sem retroativo
        mensagem = (
            f"Cobertura reativada a partir de {payload.dt_reativacao}. "
            f"Período de {nr_meses} meses sem cobertura NÃO gera cobrança retroativa (SUSEP)."
        )
        vl_devido = 0.0  # explicitamente zero — sem retroativo

    # Atualiza o registro
    cob["cd_status_cobertura"] = StatusCoberturaEnum.ATIVA
    cob["nr_meses_inadimplente"] = 0
    cob["fl_revalidado"] = True
    cob["dt_revalidacao"] = payload.dt_reativacao
    cob["dt_inicio_cobertura"] = payload.dt_reativacao  # nova vigência
    cob["ds_status_detalhado"] = mensagem

    return RevalidacaoResponse(
        nr_apolice=nr_apolice,
        cd_cpf_segurado=cpf,
        nm_segurado=cob["nm_segurado"],
        cd_status_anterior=status_anterior,
        cd_status_novo=StatusCoberturaEnum.ATIVA,
        nr_meses_inadimplente=nr_meses,
        fl_cobertura_retroativa=False,   # NUNCA retroativo
        vl_premio_devido=vl_devido,
        ds_mensagem=mensagem,
        ts_revalidacao=_now(),
    )
