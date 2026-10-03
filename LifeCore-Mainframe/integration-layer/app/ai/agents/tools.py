"""
LifeCore AI Layer — Tools para o Agente COBOL
Cada tool é uma função Python pura com schema JSON Schema (Tool Calling).

O agente recebe uma pergunta do usuário, decide quais tools chamar,
executa-as e sintetiza a resposta final.

Tools disponíveis:
  - consultar_banco       : SELECT em tabelas do PostgreSQL
  - disparar_job_cobol    : executa um job COBOL (stub/local/Zowe)
  - ler_resultado_job     : lê saída de um job já executado
  - buscar_documentacao   : RAG — busca no RUNBOOK e copybooks
  - analisar_abend        : diagnóstico de abend a partir do código
  - listar_apolices       : lista apólices por estipulante
  - calcular_capital      : chama CALCCAP via subprocesso
"""
from __future__ import annotations

import json
import logging
import subprocess
import os
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Schema de uma Tool ────────────────────────────────────────────────────────

def _tool(name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                **parameters,
            },
        },
    }


# ── Catálogo de Tools ─────────────────────────────────────────────────────────

TOOLS_SCHEMA = [

    _tool(
        name="consultar_banco",
        description=(
            "Executa uma query SQL de leitura (SELECT) no banco de dados do LifeCore. "
            "Use para buscar apólices, sinistros, faturas, pagamentos e conciliações. "
            "NUNCA use para INSERT, UPDATE, DELETE ou DDL."
        ),
        parameters={
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Query SELECT a executar. Máximo 500 caracteres.",
                },
                "justificativa": {
                    "type": "string",
                    "description": "Por que esta query é necessária.",
                },
            },
            "required": ["sql", "justificativa"],
        },
    ),

    _tool(
        name="disparar_job_cobol",
        description=(
            "Dispara um job do ciclo batch COBOL. Requer aprovação explícita do usuário "
            "para jobs que modificam dados (FATURA01, PAGTO01, CONCIL01, COMIS01). "
            "Jobs de validação (ARQVAL01) e leitura (VGCCAP01) não precisam de aprovação."
        ),
        parameters={
            "properties": {
                "nome_job": {
                    "type": "string",
                    "enum": ["ARQVAL01", "VGCCAP01", "FATURA01", "PAGTO01",
                             "CONCIL01", "COMIS01", "CLEAR01", "SETTLE01", "DISPUT01"],
                    "description": "Nome do programa COBOL a executar.",
                },
                "aprovado_pelo_usuario": {
                    "type": "boolean",
                    "description": "True somente se o usuário confirmou explicitamente.",
                },
                "parametros": {
                    "type": "object",
                    "description": "Parâmetros opcionais para o job.",
                },
            },
            "required": ["nome_job", "aprovado_pelo_usuario"],
        },
    ),

    _tool(
        name="ler_resultado_job",
        description="Lê o resultado (stdout, RC, logs) de um job já executado.",
        parameters={
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "ID do job retornado por disparar_job_cobol.",
                },
            },
            "required": ["job_id"],
        },
    ),

    _tool(
        name="buscar_documentacao",
        description=(
            "Busca semântica na documentação técnica indexada: RUNBOOK, copybooks, "
            "JCL, SQL schema e catálogo de abends. Use para responder dúvidas sobre "
            "a estrutura dos programas, layouts de arquivo e procedimentos."
        ),
        parameters={
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pergunta ou termo técnico a buscar.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Número de trechos a retornar (padrão 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),

    _tool(
        name="analisar_abend",
        description=(
            "Diagnostica um abend COBOL/z/OS a partir do código de erro. "
            "Retorna causa provável, campo suspeito, procedimento de investigação "
            "e ação corretiva, com base no catálogo de abends do RUNBOOK."
        ),
        parameters={
            "properties": {
                "codigo_abend": {
                    "type": "string",
                    "description": "Código do abend. Ex: S0C7, S0C4, S322, S806, -904, -911, -913.",
                },
                "nome_programa": {
                    "type": "string",
                    "description": "Nome do programa onde ocorreu o abend.",
                },
                "contexto": {
                    "type": "string",
                    "description": "Trecho do log ou dump relevante.",
                },
            },
            "required": ["codigo_abend"],
        },
    ),

    _tool(
        name="listar_apolices",
        description="Lista apólices ativas por empresa ou estipulante.",
        parameters={
            "properties": {
                "cd_empresa": {
                    "type": "integer",
                    "description": "Código da empresa (seguradora).",
                },
                "cd_status": {
                    "type": "string",
                    "enum": ["AT", "CA", "SU", "EX"],
                    "description": "Status da apólice: AT=Ativa, CA=Cancelada, SU=Suspensa, EX=Expirada.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de registros a retornar (padrão 20).",
                    "default": 20,
                },
            },
            "required": [],
        },
    ),

]


# ── Executor de Tools ─────────────────────────────────────────────────────────

# Catálogo de abends em memória (espelha o RUNBOOK)
_ABEND_CATALOG = {
    "S0C7": {
        "nome":       "Data Exception",
        "causa":      "Campo COMP-3 contém dados não numéricos ou corrompidos.",
        "suspeitos":  ["VL-CAPITAL", "VL-PREMIO", "VL-SALARIO", "NR-FATOR"],
        "acao":       (
            "1. Identifique o offset no dump (PSW + registrador). "
            "2. Inspecione o campo COMP-3 suspeito com IDCAMS PRINT DUMP. "
            "3. Verifique o arquivo de entrada com ARQVAL01 antes de reprocessar. "
            "4. Injete VALUE 0 nos campos numéricos não inicializados."
        ),
        "testdata":   "TESTDATA/APOLICE_S0C7.DAT",
    },
    "S0C4": {
        "nome":       "Protection Exception / Storage Violation",
        "causa":      "Acesso a endereço de memória inválido ou fora dos limites.",
        "suspeitos":  ["Índice de tabela fora dos limites", "Ponteiro nulo"],
        "acao":       (
            "1. Verifique subscritos de tabela (OCCURS). "
            "2. Confirme que o arquivo de entrada foi aberto antes de PERFORM READ. "
            "3. Valide PIC X contra PIC 9 em MOVE."
        ),
        "testdata":   None,
    },
    "S322": {
        "nome":       "CPU Time Limit Exceeded",
        "causa":      "Job excedeu o tempo de CPU configurado no JCL (TIME=).",
        "suspeitos":  ["Loop infinito", "Cursor DB2 sem CLOSE", "SORT sem SKIPREC"],
        "acao":       (
            "1. Revise condições de saída de PERFORM UNTIL. "
            "2. Feche cursores DB2 explicitamente após FETCH. "
            "3. Aumente TIME= no JCL apenas após confirmar que não é loop."
        ),
        "testdata":   None,
    },
    "S806": {
        "nome":       "Module Not Found",
        "causa":      "Programa ou módulo não encontrado na STEPLIB/LOADLIB.",
        "suspeitos":  ["CALCCAP", "módulo CALL externo"],
        "acao":       (
            "1. Verifique se CALCCAP.so está em LIFECORE/LOAD. "
            "2. Recompile com: cobc -m -I COPYLIB -o LOAD/CALCCAP SRC/COBOL/CALCCAP.cbl. "
            "3. No z/OS: confirme que o dataset LIFECORE.LOAD está na STEPLIB do JCL."
        ),
        "testdata":   None,
    },
    "-904": {
        "nome":       "SQLCODE -904: Resource Unavailable",
        "causa":      "Recurso DB2 indisponível (tablespace offline, lock timeout).",
        "suspeitos":  ["Tablespace APOLICE", "Tablespace FATURA"],
        "acao":       "Verifique o status do tablespace com DISPLAY DATABASE. Contate o DBA.",
        "testdata":   None,
    },
    "-911": {
        "nome":       "SQLCODE -911: Deadlock / Timeout",
        "causa":      "Deadlock entre transações ou timeout de lock.",
        "suspeitos":  ["FATURA01 e CONCIL01 rodando em paralelo"],
        "acao":       (
            "1. Adicione ponto de commit (EXEC SQL COMMIT) a cada 1000 registros. "
            "2. Revise a ordem de acesso às tabelas para evitar deadlock. "
            "3. Configure LOCK TIMEOUT no bind."
        ),
        "testdata":   None,
    },
    "-913": {
        "nome":       "SQLCODE -913: Unsuccessful Execution (Deadlock/Timeout)",
        "causa":      "Variante de -911 — execute rollback e reprocesse.",
        "suspeitos":  ["-911"],
        "acao":       "Execute ROLLBACK e reprocesse. Verifique DSNTRACE para detalhes.",
        "testdata":   None,
    },
}


def execute_tool(name: str, args: dict, rag_engine=None) -> dict[str, Any]:
    """
    Despacha a chamada de tool e retorna o resultado como dict.
    rag_engine é injetado quando disponível (buscar_documentacao).
    """
    try:
        if name == "consultar_banco":
            return _exec_consultar_banco(args)
        elif name == "disparar_job_cobol":
            return _exec_disparar_job(args)
        elif name == "ler_resultado_job":
            return _exec_ler_resultado(args)
        elif name == "buscar_documentacao":
            return _exec_buscar_doc(args, rag_engine)
        elif name == "analisar_abend":
            return _exec_analisar_abend(args)
        elif name == "listar_apolices":
            return _exec_listar_apolices(args)
        else:
            return {"erro": f"Tool '{name}' não reconhecida."}
    except Exception as e:
        logger.error("Erro ao executar tool %s: %s", name, e)
        return {"erro": str(e), "tool": name}


# ── Implementações ────────────────────────────────────────────────────────────

def _exec_consultar_banco(args: dict) -> dict:
    sql = args.get("sql", "").strip()

    # Guardrail: somente SELECT
    if not sql.upper().startswith("SELECT"):
        return {"erro": "Somente queries SELECT são permitidas.", "sql": sql}

    # Em produção: usar psycopg2 real
    # Aqui retornamos dados mock para demonstração
    logger.info("Executando SQL: %s", sql[:100])
    return {
        "resultado": "[stub] Query executada com sucesso.",
        "sql":       sql,
        "linhas":    0,
        "nota":      "Configure DATABASE_URL para retornar dados reais.",
    }


def _exec_disparar_job(args: dict) -> dict:
    nome_job = args["nome_job"]
    aprovado = args.get("aprovado_pelo_usuario", False)

    _JOBS_QUE_MODIFICAM = {"FATURA01", "PAGTO01", "CONCIL01", "COMIS01", "SETTLE01"}
    if nome_job in _JOBS_QUE_MODIFICAM and not aprovado:
        return {
            "erro": (
                f"O job {nome_job} modifica dados e requer aprovação explícita do usuário. "
                "Pergunte: 'Confirma a execução do job X? Isso modificará dados de produção.'"
            ),
            "requer_aprovacao": True,
            "job": nome_job,
        }

    load_dir = os.getenv("LOAD_DIR", "LOAD")
    job_path = os.path.join(load_dir, nome_job)

    if not os.path.exists(job_path):
        return {
            "aviso":    f"Executável {job_path} não encontrado — modo stub.",
            "job_id":   f"STUB-{nome_job}-{datetime.now().strftime('%H%M%S')}",
            "status":   "STUB",
            "rc":       0,
        }

    try:
        result = subprocess.run(
            [job_path],
            capture_output=True, text=True, timeout=60,
        )
        job_id = f"{nome_job}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return {
            "job_id":  job_id,
            "rc":      result.returncode,
            "stdout":  result.stdout[-2000:],  # trunca para contexto
            "stderr":  result.stderr[-500:],
            "status":  "CONCLUIDO" if result.returncode <= 4 else "ERRO",
        }
    except subprocess.TimeoutExpired:
        return {"erro": f"Job {nome_job} excedeu timeout de 60s (S322 potencial).", "job": nome_job}


def _exec_ler_resultado(args: dict) -> dict:
    job_id = args["job_id"]
    output_dir = os.getenv("DATA_OUTPUT_DIR", "/tmp/lifecore/OUTPUT")
    result_file = os.path.join(output_dir, f"{job_id}.result")

    if not os.path.exists(result_file):
        return {"aviso": f"Arquivo de resultado não encontrado: {result_file}", "job_id": job_id}

    content = Path(result_file).read_text(errors="replace")[:3000]
    return {"job_id": job_id, "conteudo": content}


def _exec_buscar_doc(args: dict, rag_engine) -> dict:
    query = args["query"]
    top_k = args.get("top_k", 5)

    if rag_engine is None:
        return {"aviso": "RAG Engine não inicializado.", "query": query}

    chunks = rag_engine.retrieve(query, top_k=top_k)
    return {
        "query":    query,
        "chunks":   [
            {"fonte": c.metadata.get("source", "?"), "score": round(c.score, 3), "texto": c.text[:400]}
            for c in chunks
        ],
        "total":    len(chunks),
    }


def _exec_analisar_abend(args: dict) -> dict:
    codigo = args["codigo_abend"].upper().strip()
    programa = args.get("nome_programa", "desconhecido")
    contexto = args.get("contexto", "")

    info = _ABEND_CATALOG.get(codigo)
    if not info:
        return {
            "codigo": codigo,
            "aviso":  f"Código {codigo} não está no catálogo local. Consulte o RUNBOOK completo.",
        }

    return {
        "codigo":    codigo,
        "nome":      info["nome"],
        "causa":     info["causa"],
        "campos_suspeitos": info["suspeitos"],
        "acao_corretiva":   info["acao"],
        "programa":  programa,
        "testdata":  info.get("testdata"),
        "contexto_fornecido": contexto[:300] if contexto else None,
    }


def _exec_listar_apolices(args: dict) -> dict:
    # Stub — em produção faz query real
    return {
        "apolices": [
            {"nr_apolice": "2026.APO.000001", "cd_status": "AT", "cd_produto": "VGC"},
        ],
        "nota": "Configure DATABASE_URL para retornar dados reais.",
        "filtros_aplicados": args,
    }


# Necessário para _exec_ler_resultado
from pathlib import Path
