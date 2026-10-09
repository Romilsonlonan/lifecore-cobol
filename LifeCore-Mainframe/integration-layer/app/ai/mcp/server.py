"""
LifeCore AI Layer — MCP Server
Expõe as ferramentas do LifeCore via Model Context Protocol (MCP).

O MCP permite que qualquer LLM-client compatível (Claude Desktop, Cursor,
Continue.dev, etc.) use as ferramentas do LifeCore sem precisar de código
de integração customizado.

Transporte: stdio (padrão MCP) — compatível com Claude Desktop e Zed.
Para HTTP/SSE use: mcp.run(transport="sse", port=8001)

Ferramentas expostas:
  lifecore_rag_query      — consulta RAG no RUNBOOK
  lifecore_analisar_abend — diagnóstico de abend
  lifecore_listar_apolices — lista apólices
  lifecore_disparar_job   — dispara job COBOL (com guardrail)
  lifecore_consultar_banco — consulta SQL (somente SELECT)

Recursos (Resources):
  runbook://abends          — catálogo de abends
  runbook://copybooks/{nome} — layout de um copybook

Prompts:
  diagnosticar_abend        — template para análise de abend
  revisar_job_faturamento   — checklist pré-execução do FATURA01
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def build_mcp_server():
    """
    Constrói e retorna o MCP Server do LifeCore.
    Requer: pip install mcp
    """
    try:
        from mcp.server import FastMCP
    except ImportError:
        logger.warning(
            "mcp não instalado. Instale com: pip install mcp\n"
            "O servidor MCP não estará disponível."
        )
        return None

    from app.ai.agents.tools import _ABEND_CATALOG, execute_tool
    from app.ai.rag.engine import get_rag_engine

    mcp = FastMCP(
        name="lifecore-mainframe",
        version="2.0.0",
        instructions=(
            "Servidor MCP do LifeCore-Mainframe. "
            "Fornece acesso ao sistema de seguros de vida em grupo (VGC/GLB), "
            "diagnóstico de abends COBOL e operações do ciclo batch z/OS."
        ),
    )

    # ── Tools ─────────────────────────────────────────────────────────────────

    @mcp.tool()
    def lifecore_rag_query(query: str, top_k: int = 5) -> str:
        """
        Consulta semântica na documentação técnica do LifeCore:
        RUNBOOK de abends, copybooks, JCL, SQL schema.
        Retorna os trechos mais relevantes com fonte e score.
        """
        engine = get_rag_engine()
        chunks = engine.retrieve(query, top_k=top_k)
        if not chunks:
            return "Nenhum documento indexado. Execute a indexação primeiro."
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(
                f"[{i}] {c.metadata.get('source','?')} (score={c.score:.3f})\n{c.text[:500]}"
            )
        return "\n\n---\n\n".join(lines)

    @mcp.tool()
    def lifecore_analisar_abend(
        codigo_abend: str,
        nome_programa: str = "desconhecido",
        contexto: str = "",
    ) -> str:
        """
        Diagnostica um abend COBOL/z/OS.
        Códigos suportados: S0C7, S0C4, S322, S806, -904, -911, -913.
        Retorna causa, campos suspeitos e ação corretiva.
        """
        result = execute_tool(
            "analisar_abend",
            {
                "codigo_abend": codigo_abend,
                "nome_programa": nome_programa,
                "contexto": contexto,
            },
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def lifecore_listar_apolices(
        cd_empresa: int = 1,
        cd_status: str = "AT",
        limite: int = 20,
    ) -> str:
        """
        Lista apólices do LifeCore por empresa e status.
        Status: AT=Ativa, CA=Cancelada, SU=Suspensa, EX=Expirada.
        """
        result = execute_tool(
            "listar_apolices",
            {"cd_empresa": cd_empresa, "cd_status": cd_status, "limite": limite},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def lifecore_disparar_job(
        nome_job: str,
        aprovado_pelo_usuario: bool = False,
    ) -> str:
        """
        Dispara um job do ciclo batch COBOL.
        Jobs que modificam dados (FATURA01, PAGTO01, CONCIL01, COMIS01)
        exigem aprovado_pelo_usuario=True.
        """
        result = execute_tool(
            "disparar_job_cobol",
            {"nome_job": nome_job, "aprovado_pelo_usuario": aprovado_pelo_usuario},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    def lifecore_consultar_banco(sql: str, justificativa: str) -> str:
        """
        Executa uma query SELECT no banco de dados do LifeCore.
        Apenas leitura — INSERT/UPDATE/DELETE são bloqueados.
        """
        result = execute_tool(
            "consultar_banco",
            {"sql": sql, "justificativa": justificativa},
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Resources ─────────────────────────────────────────────────────────────

    @mcp.resource("runbook://abends")
    def resource_abend_catalog() -> str:
        """Catálogo completo de abends do LifeCore-Mainframe."""
        lines = ["# Catálogo de Abends — LifeCore-Mainframe\n"]
        for codigo, info in _ABEND_CATALOG.items():
            lines.append(f"## {codigo} — {info['nome']}")
            lines.append(f"**Causa:** {info['causa']}")
            lines.append(f"**Campos suspeitos:** {', '.join(info['suspeitos'])}")
            lines.append(f"**Ação:** {info['acao']}\n")
        return "\n".join(lines)

    @mcp.resource("runbook://copybooks/{nome}")
    def resource_copybook(nome: str) -> str:
        """Retorna o conteúdo de um copybook pelo nome (ex: CPYAPOL, CPYFATU)."""
        copylib = os.path.join(
            os.getenv("PROJECT_ROOT", "/app"),
            "COPYLIB",
            f"{nome.upper()}.cpy",
        )
        try:
            with open(copylib, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"Copybook {nome}.cpy não encontrado em {copylib}."

    # ── Prompts ───────────────────────────────────────────────────────────────

    @mcp.prompt()
    def diagnosticar_abend(
        codigo: str, programa: str, log_trecho: str = ""
    ) -> list[dict]:
        """Template de análise de abend para o assistente."""
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Preciso diagnosticar um abend {codigo} no programa {programa}.\n\n"
                        f"Trecho do log:\n```\n{log_trecho}\n```\n\n"
                        "Por favor:\n"
                        "1. Identifique a causa provável\n"
                        "2. Indique os campos COBOL suspeitos\n"
                        "3. Descreva o procedimento de investigação\n"
                        "4. Sugira a correção"
                    ),
                },
            }
        ]

    @mcp.prompt()
    def revisar_job_faturamento() -> list[dict]:
        """Checklist pré-execução do ciclo de faturamento."""
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Antes de executar o ciclo de faturamento (FATURA01), "
                        "verifique os seguintes pontos:\n\n"
                        "1. O ARQVAL01 foi executado e o RC foi ≤ 4?\n"
                        "2. Existem registros em quarentena que precisam de correção?\n"
                        "3. O mês de referência está correto nos parâmetros?\n"
                        "4. O backup do dataset de entrada foi feito?\n"
                        "5. O banco de dados DB2/PostgreSQL está acessível?\n\n"
                        "Responda item a item com base no estado atual do sistema."
                    ),
                },
            }
        ]

    return mcp
