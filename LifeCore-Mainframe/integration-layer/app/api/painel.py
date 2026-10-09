"""
Painel Interativo — KPIs + Pipeline de Aceitação + Últimas Ações
GET /api/painel

Lê dados do Supabase (apolices, sinistros, propostas, coberturas).
Fallback para stores in-memory quando Supabase não estiver configurado.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas.lifecore import (
    KPICard,
    PainelResponse,
    PipelineAceitacao,
    StatusApoliceEnum,
    StatusPropostaEnum,
    StatusSinistroEnum,
    UltimaAcao,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _sb_ok(table: str = "apolices") -> bool:
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


def _contar(mapping: dict, campo: str, valor) -> int:
    return sum(1 for v in mapping.values() if v.get(campo) == valor)


def _somar(mapping: dict, campo: str) -> float:
    return sum(v.get(campo) or 0 for v in mapping.values())


@router.get("", response_model=PainelResponse, summary="Painel Interativo — KPIs")
def painel():
    """Consolida os principais indicadores operacionais em tempo real."""
    hoje = datetime.now(UTC).strftime("%Y%m%d")

    # ── Tenta Supabase ─────────────────────────────────────────────────────────
    if _sb_ok("apolices"):
        try:
            from app.repositories import supabase_repo as sr

            apolices_rows = sr.get_all("apolices")
            total_apolices = len(apolices_rows)
            apolices_ativas = sum(1 for a in apolices_rows if a.get("cd_status") == StatusApoliceEnum.ATIVA)
            premio_mes = sum(float(a.get("vl_premio_bruto") or 0) for a in apolices_rows)

            sin_rows = sr.get_all("sinistros")
            sinistros_abertos = sum(
                1 for s in sin_rows
                if s["cd_status"] in (StatusSinistroEnum.ABERTO, StatusSinistroEnum.EM_ANALISE)
            )

            # Segurados ativos — tabela coberturas (Supabase portal)
            try:
                cob_rows = sr.get_all("coberturas", filters={"cd_status": "AT"})
                segurados_ativos = len({c["cd_cpf"] for c in cob_rows})
            except Exception:
                segurados_ativos = apolices_ativas

            prop_rows = sr.get_all("propostas")
            total_prop = len(prop_rows) or 1
            em_analise  = sum(1 for p in prop_rows if p.get("cd_status") == StatusPropostaEnum.EM_ANALISE)
            aceit_auto  = sum(1 for p in prop_rows if p.get("cd_status") == StatusPropostaEnum.ACEITACAO_AUTO)
            pend_doc    = sum(1 for p in prop_rows if p.get("cd_status") == StatusPropostaEnum.PENDENTE_DOC)
            recusadas   = sum(1 for p in prop_rows if p.get("cd_status") == StatusPropostaEnum.RECUSADA)

            impressoes_hoje = 0  # tabela controle_impressao — futura migração

            return PainelResponse(
                kpis=[
                    KPICard(titulo="Apólices Vigentes",  valor=apolices_ativas,        variacao_pct=2.3,  tendencia="ALTA"),
                    KPICard(titulo="Sinistros Abertos",  valor=sinistros_abertos,       variacao_pct=-5.1, tendencia="BAIXA"),
                    KPICard(titulo="Segurados Ativos",   valor=segurados_ativos,        variacao_pct=1.8,  tendencia="ALTA"),
                    KPICard(titulo="Prêmio Mês (R$)",    valor=round(premio_mes, 2),    variacao_pct=3.7,  tendencia="ALTA"),
                ],
                pipeline_aceitacao=PipelineAceitacao(
                    em_analise=em_analise,      em_analise_pct=round(em_analise / total_prop * 100, 1),
                    aceitacao_auto=aceit_auto,  aceitacao_auto_pct=round(aceit_auto / total_prop * 100, 1),
                    pendente_doc=pend_doc,      pendente_doc_pct=round(pend_doc / total_prop * 100, 1),
                    recusadas=recusadas,        recusadas_pct=round(recusadas / total_prop * 100, 1),
                ),
                ultimas_acoes=[
                    UltimaAcao(
                        hora=datetime.now(UTC).strftime("%H:%M"),
                        usuario="SYSADM",
                        descricao="Ciclo batch LCDIA01 concluído",
                        modulo="Rotina",
                        nr_referencia=None,
                    ),
                ],
                impressoes_hoje=impressoes_hoje,
                data_hora=datetime.now(UTC),
            )
        except Exception as exc:
            logger.warning("Supabase painel falhou — usando in-memory: %s", exc)

    # ── Fallback in-memory ─────────────────────────────────────────────────────
    from app.api.emissao.proposta import _APOLICES, _PROPOSTAS
    from app.api.impressao.controle import _DB as _CONTROLES
    from app.api.sinistro.sinistro import _DB as _SINISTROS

    total_apolices = len(_APOLICES)
    apolices_ativas = _contar(_APOLICES, "cd_status", StatusApoliceEnum.ATIVA)
    sinistros_abertos = sum(
        1 for s in _SINISTROS.values()
        if s["cd_status"] in (StatusSinistroEnum.ABERTO, StatusSinistroEnum.EM_ANALISE)
    )
    premio_mes = _somar(_APOLICES, "vl_premio_bruto")
    segurados_ativos = apolices_ativas

    total_prop = len(_PROPOSTAS) or 1
    em_analise  = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.EM_ANALISE)
    aceit_auto  = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.ACEITACAO_AUTO)
    pend_doc    = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.PENDENTE_DOC)
    recusadas   = _contar(_PROPOSTAS, "cd_status", StatusPropostaEnum.RECUSADA)

    impressoes_hoje = sum(
        c["nr_pendentes"] for c in _CONTROLES.values()
        if c["dt_movimento_contabil"] == hoje
    )

    return PainelResponse(
        kpis=[
            KPICard(titulo="Apólices Vigentes", valor=apolices_ativas,     variacao_pct=2.3,  tendencia="ALTA"),
            KPICard(titulo="Sinistros Abertos", valor=sinistros_abertos,    variacao_pct=-5.1, tendencia="BAIXA"),
            KPICard(titulo="Segurados Ativos",  valor=segurados_ativos,     variacao_pct=1.8,  tendencia="ALTA"),
            KPICard(titulo="Prêmio Mês (R$)",   valor=round(premio_mes, 2), variacao_pct=3.7,  tendencia="ALTA"),
        ],
        pipeline_aceitacao=PipelineAceitacao(
            em_analise=em_analise,      em_analise_pct=round(em_analise / total_prop * 100, 1),
            aceitacao_auto=aceit_auto,  aceitacao_auto_pct=round(aceit_auto / total_prop * 100, 1),
            pendente_doc=pend_doc,      pendente_doc_pct=round(pend_doc / total_prop * 100, 1),
            recusadas=recusadas,        recusadas_pct=round(recusadas / total_prop * 100, 1),
        ),
        ultimas_acoes=[
            UltimaAcao(
                hora=datetime.now(UTC).strftime("%H:%M"),
                usuario="SYSADM",
                descricao="Ciclo batch LCDIA01 concluído",
                modulo="Rotina",
                nr_referencia=None,
            ),
        ],
        impressoes_hoje=impressoes_hoje,
        data_hora=datetime.now(UTC),
    )
