"""
Portal — Dashboard Gerencial dos 18 Agentes LifeCore IQ
GET /api/portal/agentes

Retorna o status operacional de cada agente baseado nas tabelas Supabase:
- issues_abertas  → registros criados/pendentes nas tabelas do agente
- issues_feitas   → registros processados/concluídos
- ultima_atividade → timestamp mais recente de qualquer operação do agente
Sem dados reais de Jira — usa as tabelas do próprio projeto como proxy.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


def _sb():
    from app.services.supabase_client import get_client

    return get_client()


# Catálogo dos 18 agentes com suas tabelas de referência no Supabase
_AGENTES: list[dict] = [
    {
        "slug": "fat",
        "nome": "Faturamento",
        "emoji": "🧾",
        "grupo": "Negócio",
        "tabela": "faturas",
        "campo_status": "cd_status",
        "done_vals": ["OK", "PG"],
        "descricao": "Geração de faturas mensais e reajuste IPCA",
    },
    {
        "slug": "ren",
        "nome": "Renovação",
        "emoji": "🔄",
        "grupo": "Negócio",
        "tabela": "historico_apolice",
        "campo_status": "tp_acao",
        "done_vals": ["RENOVACAO"],
        "descricao": "Renovação automática e manual de apólices",
    },
    {
        "slug": "sus",
        "nome": "Sustentação",
        "emoji": "🛠️",
        "grupo": "Operações",
        "tabela": None,
        "campo_status": None,
        "done_vals": [],
        "descricao": "Incidentes produção, diagnóstico de ABENDs",
    },
    {
        "slug": "mlc",
        "nome": "Melhoria Contínua",
        "emoji": "🚀",
        "grupo": "Conformidade",
        "tabela": None,
        "campo_status": None,
        "done_vals": [],
        "descricao": "Tech debt, refatorações, SLA de batch",
    },
    {
        "slug": "prd",
        "nome": "Produto",
        "emoji": "📦",
        "grupo": "Negócio",
        "tabela": "propostas",
        "campo_status": "cd_status",
        "done_vals": ["AP", "AA"],
        "descricao": "Catálogo VGC/GLB, tipos de capital F/E/M/B/P",
    },
    {
        "slug": "seg",
        "nome": "Segurados",
        "emoji": "👥",
        "grupo": "Negócio",
        "tabela": "coberturas",
        "campo_status": "cd_status",
        "done_vals": ["AT"],
        "descricao": "Cadastro, movimentações INC/EXC/CAP/SUS/REA",
    },
    {
        "slug": "cor",
        "nome": "Corretagem",
        "emoji": "🤝",
        "grupo": "Negócio",
        "tabela": "corretores",
        "campo_status": "cd_status",
        "done_vals": ["AT"],
        "descricao": "Corretores, vínculos, produção",
    },
    {
        "slug": "com",
        "nome": "Comissões",
        "emoji": "💰",
        "grupo": "Negócio",
        "tabela": "vinculos",
        "campo_status": "cd_status",
        "done_vals": ["AT"],
        "descricao": "Cálculo e conferência de comissões",
    },
    {
        "slug": "sin",
        "nome": "Sinistros",
        "emoji": "⚖️",
        "grupo": "Negócio",
        "tabela": "sinistros",
        "campo_status": "cd_status",
        "done_vals": ["PA", "EN"],
        "descricao": "Abertura, análise e detecção de fraude",
    },
    {
        "slug": "cnc",
        "nome": "Conciliação",
        "emoji": "🔄",
        "grupo": "Negócio",
        "tabela": "faturas",
        "campo_status": "cd_status",
        "done_vals": ["PG", "LQ"],
        "descricao": "Faturado×pago, clearing, chargebacks",
    },
    {
        "slug": "arq",
        "nome": "Arquivos",
        "emoji": "📁",
        "grupo": "Operações",
        "tabela": "importacao_vidas",
        "campo_status": "cd_status",
        "done_vals": ["OK"],
        "descricao": "Importação batch, validação, GDGs",
    },
    {
        "slug": "int",
        "nome": "Integrações",
        "emoji": "🔌",
        "grupo": "Operações",
        "tabela": "estipulantes",
        "campo_status": "cd_status",
        "done_vals": ["AT", "VI"],
        "descricao": "APIs REST, migração Supabase, i4Pro",
    },
    {
        "slug": "qdt",
        "nome": "Qualidade Dados",
        "emoji": "🔎",
        "grupo": "Operações",
        "tabela": "coberturas",
        "campo_status": "cd_status",
        "done_vals": ["AT"],
        "descricao": "Duplicidades, inconsistências, integridade",
    },
    {
        "slug": "bia",
        "nome": "BI/Inteligência",
        "emoji": "📊",
        "grupo": "Inteligência",
        "tabela": "importacao_vidas",
        "campo_status": "cd_status",
        "done_vals": ["OK", "PA"],
        "descricao": "KPIs, sinistralidade, tendências",
    },
    {
        "slug": "gov",
        "nome": "Governança",
        "emoji": "🔐",
        "grupo": "Conformidade",
        "tabela": "historico_apolice",
        "campo_status": "tp_acao",
        "done_vals": ["CANCELAMENTO", "ENDOSSO"],
        "descricao": "LGPD, SUSEP, PCI-DSS, auditoria",
    },
    {
        "slug": "qat",
        "nome": "QA/Testes",
        "emoji": "🧪",
        "grupo": "Conformidade",
        "tabela": "criticas_pendentes",
        "campo_status": "cd_status",
        "done_vals": ["LI", "RE"],
        "descricao": "267 testes pytest, CI/CD 8 jobs",
    },
    {
        "slug": "rag",
        "nome": "Knowledge/RAG",
        "emoji": "🤖",
        "grupo": "Inteligência",
        "tabela": None,
        "campo_status": None,
        "done_vals": [],
        "descricao": "Base de conhecimento, RAG engine",
    },
    {
        "slug": "orc",
        "nome": "Orquestrador",
        "emoji": "🧠",
        "grupo": "Inteligência",
        "tabela": None,
        "campo_status": None,
        "done_vals": [],
        "descricao": "Sprint planning, distribuição de tarefas",
    },
]

_GRUPOS_ORDEM = ["Negócio", "Operações", "Inteligência", "Conformidade"]


def _query_tabela(tabela: str, campo: str, done_vals: list[str]) -> tuple[int, int, str]:
    """Retorna (abertas, feitas, ultima_atividade) para uma tabela."""
    try:
        sb = _sb()
        res = sb.table(tabela).select(campo).limit(500).execute()
        rows = res.data or []
        feitas = sum(1 for r in rows if r.get(campo) in done_vals)
        abertas = len(rows) - feitas

        # última atividade: tenta ts_inclusao, dt_cadastro ou updated_at
        for ts_col in ("ts_inclusao", "dt_cadastro", "updated_at", "created_at"):
            res2 = sb.table(tabela).select(ts_col).order(ts_col, desc=True).limit(1).execute()
            if res2.data and res2.data[0].get(ts_col):
                return abertas, feitas, str(res2.data[0][ts_col])[:16]
        return abertas, feitas, "—"
    except Exception as exc:
        logger.debug("agentes – tabela %s falhou: %s", tabela, exc)
        return 0, 0, "—"


@router.get("", summary="Dashboard Gerencial — 18 Agentes LifeCore IQ")
def agentes() -> dict:
    resultado: list[dict] = []
    agora = datetime.now(UTC).isoformat()

    for ag in _AGENTES:
        if ag["tabela"]:
            abertas, feitas, ultima = _query_tabela(
                ag["tabela"], ag["campo_status"], ag["done_vals"]
            )
        else:
            abertas, feitas, ultima = 0, 0, "—"

        total = abertas + feitas
        pct = round(feitas / total * 100) if total > 0 else 0

        resultado.append(
            {
                "slug": ag["slug"],
                "nome": ag["nome"],
                "emoji": ag["emoji"],
                "grupo": ag["grupo"],
                "descricao": ag["descricao"],
                "issues_abertas": abertas,
                "issues_feitas": feitas,
                "total": total,
                "pct_concluido": pct,
                "ultima_atividade": ultima,
                "branch_padrao": _branch(ag["slug"]),
            }
        )

    # Agrupar por grupo na ordem definida
    grupos: list[dict] = []
    for g in _GRUPOS_ORDEM:
        membros = [a for a in resultado if a["grupo"] == g]
        grupos.append({"grupo": g, "agentes": membros})

    return {
        "grupos": grupos,
        "total_agentes": len(resultado),
        "gerado_em": agora,
    }


def _branch(slug: str) -> str:
    prefixos = {
        "sus": "fix",
        "mlc": "chore",
        "gov": "chore",
        "orc": "chore",
        "rag": "docs",
        "qat": "fix",
    }
    return f"{prefixos.get(slug, 'feat')}/{slug}/LCIQ-###-descricao"
