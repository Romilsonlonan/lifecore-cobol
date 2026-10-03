"""
Painel Interativo — KPIs + Pipeline de Aceitação + Últimas Ações
GET /api/painel
"""
from datetime import datetime
from fastapi import APIRouter

from app.schemas.lifecore import (
    PainelResponse,
    KPICard,
    PipelineAceitacao,
    UltimaAcao,
    StatusPropostaEnum,
    StatusSinistroEnum,
    StatusApoliceEnum,
)

# Imports dos stores in-memory dos outros módulos
from app.api.emissao.proposta import _PROPOSTAS, _APOLICES
from app.api.sinistro.sinistro import _DB as _SINISTROS
from app.api.impressao.controle import _DB as _CONTROLES

router = APIRouter()


def _contar(mapping: dict, campo: str, valor) -> int:
    return sum(1 for v in mapping.values() if v.get(campo) == valor)


def _somar(mapping: dict, campo: str) -> float:
    return sum(v.get(campo) or 0 for v in mapping.values())


@router.get("", response_model=PainelResponse, summary="Painel Interativo — KPIs")
def painel():
    """
    Consolida os principais indicadores operacionais em tempo real.
    Em produção, substitua os stores in-memory por queries SQLAlchemy.
    """
    # ── Contagens base ────────────────────────────────────────────────
    total_apolices   = len(_APOLICES)
    apolices_ativas  = _contar(_APOLICES, "cd_status", StatusApoliceEnum.ATIVA)
    sinistros_abertos = sum(
        1 for s in _SINISTROS.values()
        if s["cd_status"] in (StatusSinistroEnum.ABERTO, StatusSinistroEnum.EM_ANALISE)
    )
    premio_mes       = _somar(_APOLICES, "vl_premio_bruto")
    segurados_ativos = apolices_ativas   # 1 apólice = 1 segurado no stub

    # ── KPI Cards ─────────────────────────────────────────────────────
    kpis = [
        KPICard(
            titulo="Apólices Vigentes",
            valor=apolices_ativas,
            variacao_pct=2.3,
            tendencia="ALTA",
        ),
        KPICard(
            titulo="Sinistros Abertos",
            valor=sinistros_abertos,
            variacao_pct=-5.1,
            tendencia="BAIXA",
        ),
        KPICard(
            titulo="Segurados Ativos",
            valor=segurados_ativos,
            variacao_pct=1.8,
            tendencia="ALTA",
        ),
        KPICard(
            titulo="Prêmio Mês (R$)",
            valor=round(premio_mes, 2),
            variacao_pct=3.7,
            tendencia="ALTA",
        ),
    ]

    # ── Pipeline de Aceitação ─────────────────────────────────────────
    total_prop = len(_PROPOSTAS) or 1   # evitar divisão por zero
    em_analise     = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.EM_ANALISE)
    aceit_auto     = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.ACEITACAO_AUTO)
    pend_doc       = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.PENDENTE_DOC)
    recusadas      = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.RECUSADA)

    pipeline = PipelineAceitacao(
        em_analise=em_analise,
        em_analise_pct=round(em_analise / total_prop * 100, 1),
        aceitacao_auto=aceit_auto,
        aceitacao_auto_pct=round(aceit_auto / total_prop * 100, 1),
        pendente_doc=pend_doc,
        pendente_doc_pct=round(pend_doc / total_prop * 100, 1),
        recusadas=recusadas,
        recusadas_pct=round(recusadas / total_prop * 100, 1),
    )

    # ── Últimas Ações (stub fixo — em produção: query AUDITORIA_ACAO) ─
    ultimas_acoes = [
        UltimaAcao(
            hora=datetime.utcnow().strftime("%H:%M"),
            usuario="SYSADM",
            descricao="Ciclo batch LCDIA01 concluído",
            modulo="Rotina",
            nr_referencia=None,
        ),
    ]

    # ── Impressões pendentes hoje ──────────────────────────────────────
    hoje = datetime.today().strftime("%Y%m%d")
    impressoes_hoje = sum(
        c["nr_pendentes"]
        for c in _CONTROLES.values()
        if c["dt_movimento_contabil"] == hoje
    )

    return PainelResponse(
        kpis=kpis,
        pipeline_aceitacao=pipeline,
        ultimas_acoes=ultimas_acoes,
        impressoes_hoje=impressoes_hoje,
        data_hora=datetime.utcnow(),
    )
