"""
AI Layer — Router FastAPI
Expõe todos os endpoints da camada de IA do LifeCore.

GET  /api/ai/health          — status da AI Layer
POST /api/ai/rag/index       — indexa diretório do projeto
POST /api/ai/rag/query       — consulta RAG
POST /api/ai/agent/run       — executa o agente COBOL
POST /api/ai/abend/analisar  — diagnóstico de abend (sem LLM)
POST /api/ai/guardrails/check — verifica uma mensagem pelos guardrails
GET  /api/ai/evals/run       — executa a suite de avaliação
GET  /api/ai/finetune/dataset — baixa o dataset de fine-tuning
"""
from __future__ import annotations

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    directory: str = Field(
        default=".",
        description="Diretório relativo ao PROJECT_ROOT para indexar.",
    )
    recursive: bool = True


class RAGQueryRequest(BaseModel):
    query:  str   = Field(..., description="Pergunta técnica.")
    top_k:  int   = Field(5, ge=1, le=20)
    use_llm: bool = Field(False, description="Se True, usa LLM para gerar resposta.")


class AgentRequest(BaseModel):
    message:  str                    = Field(..., description="Mensagem do usuário.")
    user_id:  str                    = Field("anonymous", max_length=40)
    history:  Optional[list[dict]]   = None


class AbendRequest(BaseModel):
    codigo_abend:  str           = Field(..., description="Ex: S0C7, -911")
    nome_programa: Optional[str] = None
    contexto:      Optional[str] = None


class GuardrailCheckRequest(BaseModel):
    user_id: str = "anonymous"
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health", summary="Status da AI Layer")
def ai_health():
    """Verifica dependências da AI Layer sem inicializar os modelos."""
    status = {}
    try:
        from sentence_transformers import SentenceTransformer  # noqa
        status["sentence_transformers"] = "ok"
    except ImportError:
        status["sentence_transformers"] = "não instalado"

    try:
        import chromadb  # noqa
        status["chromadb"] = "ok"
    except ImportError:
        status["chromadb"] = "não instalado"

    try:
        from openai import OpenAI  # noqa
        status["openai_sdk"] = "ok"
    except ImportError:
        status["openai_sdk"] = "não instalado"

    try:
        import mcp  # noqa
        status["mcp"] = "ok"
    except ImportError:
        status["mcp"] = "não instalado (opcional)"

    all_critical = status["sentence_transformers"] == "ok" and status["chromadb"] == "ok"
    return {
        "status":       "ok" if all_critical else "degradado",
        "dependencias": status,
        "nota":         "LLM_BASE_URL e LLM_MODEL são configurados via .env",
    }


@router.post("/rag/index", summary="Indexa documentos no vector store")
def rag_index(req: IndexRequest, background_tasks: BackgroundTasks):
    """
    Indexa todos os arquivos reconhecidos no diretório especificado.
    Roda em background — retorna job_id imediatamente.
    """
    import os, uuid
    from app.ai.rag.engine import get_rag_engine, Indexer

    project_root = os.getenv("PROJECT_ROOT", "/app")
    target = Path(project_root) / req.directory

    if not target.exists():
        raise HTTPException(404, detail=f"Diretório não encontrado: {target}")

    job_id = f"IDX-{uuid.uuid4().hex[:8].upper()}"

    def _index():
        engine  = get_rag_engine()
        indexer = Indexer(engine._embedder, engine._store)
        totals  = indexer.index_directory(target, recursive=req.recursive)
        logger.info("Indexação %s concluída: %d arquivos", job_id, len(totals))

    background_tasks.add_task(_index)

    return {
        "job_id":    job_id,
        "status":    "INDEXANDO",
        "directory": str(target),
        "mensagem":  "Indexação iniciada em background.",
    }


@router.post("/rag/query", summary="Consulta semântica (RAG)")
def rag_query(req: RAGQueryRequest):
    """
    Busca os trechos mais relevantes para a pergunta.
    Com use_llm=True, gera uma resposta sintetizada pelo LLM.
    """
    from app.ai.rag.engine import get_rag_engine

    engine = get_rag_engine()

    if req.use_llm:
        result = engine.generate(req.query, top_k=req.top_k)
        return {
            "query":         result.query,
            "answer":        result.answer,
            "model_used":    result.model_used,
            "context_tokens": result.context_tokens,
            "sources": [
                {
                    "fonte": c.metadata.get("source", "?"),
                    "score": round(c.score, 3),
                    "trecho": c.text[:300],
                }
                for c in result.sources
            ],
        }
    else:
        chunks = engine.retrieve(req.query, top_k=req.top_k)
        return {
            "query":   req.query,
            "chunks":  [
                {
                    "fonte":  c.metadata.get("source", "?"),
                    "score":  round(c.score, 3),
                    "trecho": c.text[:300],
                }
                for c in chunks
            ],
            "total": len(chunks),
        }


@router.post("/agent/run", summary="Executa o Agente COBOL (Tool Calling)")
def agent_run(req: AgentRequest):
    """
    Executa o agente COBOL com loop ReAct e Tool Calling.
    O agente pode chamar múltiplas tools antes de gerar a resposta final.

    Guardrails são aplicados automaticamente:
    - Input: prompt injection, SQL destrutivo, tamanho
    - Action: jobs destrutivos requerem aprovação
    - Output: PAN/CPF mascarados
    """
    from app.ai.guardrails.pipeline import get_guardrails
    from app.ai.agents.agent import build_agent
    from app.ai.rag.engine import get_rag_engine

    guardrails = get_guardrails()

    # Input guardrail
    check = guardrails.check_input(req.user_id, req.message)
    if not check.allowed:
        raise HTTPException(400, detail=check.reason)

    # Executa agente
    rag    = get_rag_engine()
    agent  = build_agent(rag_engine=rag)
    result = agent.run(req.message, conversation_history=req.history)

    # Output guardrail
    safe = guardrails.sanitize_output(result.answer)

    return {
        "answer":     safe.sanitized,
        "tool_calls": result.tool_calls,
        "steps":      [
            {
                "turn":      s.turn,
                "tool":      s.tool_name,
                "args":      s.tool_args,
                "result":    s.tool_result,
            }
            for s in result.steps if s.tool_name
        ],
        "error":      result.error,
        "sanitized":  safe.risk_score > 0,
    }


@router.post("/abend/analisar", summary="Diagnóstico de abend COBOL (sem LLM)")
def analisar_abend(req: AbendRequest):
    """
    Retorna diagnóstico imediato de um abend a partir do catálogo local.
    Não requer LLM — resposta instantânea.
    """
    from app.ai.agents.tools import execute_tool
    result = execute_tool("analisar_abend", {
        "codigo_abend":  req.codigo_abend,
        "nome_programa": req.nome_programa or "desconhecido",
        "contexto":      req.contexto or "",
    })
    # "aviso" = abend não está no catálogo (retorna 200 com aviso)
    # "erro"  = erro interno inesperado
    if "erro" in result and "aviso" not in result:
        raise HTTPException(500, detail=result["erro"])
    return result


@router.post("/guardrails/check", summary="Verifica mensagem pelos guardrails")
def guardrail_check(req: GuardrailCheckRequest):
    """
    Verifica se uma mensagem passaria pelos guardrails de input.
    Útil para testar/demonstrar a camada de segurança.
    """
    from app.ai.guardrails.pipeline import get_guardrails
    g = get_guardrails()
    result = g.check_input(req.user_id, req.message)
    return {
        "allowed":    result.allowed,
        "reason":     result.reason,
        "risk_score": result.risk_score,
    }


@router.get("/evals/run", summary="Executa suite de avaliação (rule-based)")
def evals_run():
    """
    Executa o dataset de avaliação contra o agente com RuleBasedEvaluator.
    Não requer LLM — baseado em heurísticas.
    """
    from app.ai.evals.evaluator import RuleBasedEvaluator, EVAL_DATASET

    evaluator = RuleBasedEvaluator()
    results = []

    for item in EVAL_DATASET:
        # Usa o gold standard como "resposta" para testar o evaluator
        result = evaluator.evaluate(
            question=item["question"],
            answer=item["gold"],
            gold=item["gold"],
        )
        results.append({
            "id":      item["id"],
            "category": item["category"],
            **result.summary(),
        })

    avg = sum(r["overall"] for r in results) / max(1, len(results))
    return {
        "total":    len(results),
        "avg_score": round(avg, 3),
        "results":  results,
    }


@router.get("/finetune/dataset", summary="Baixa o dataset de fine-tuning")
def finetune_dataset(fmt: str = "chatml"):
    """
    Retorna o dataset de fine-tuning no formato especificado.
    Formatos: chatml (padrão) | alpaca | sharegpt
    """
    from app.ai.finetune.dataset import build_dataset, get_stats

    if fmt not in ("chatml", "alpaca", "sharegpt"):
        raise HTTPException(400, detail=f"Formato '{fmt}' inválido. Use: chatml, alpaca, sharegpt.")

    dataset = build_dataset(fmt)
    return {
        "format":   fmt,
        "stats":    get_stats(dataset if fmt == "chatml" else None),
        "dataset":  dataset,
    }
