"""
LifeCore-Mainframe — Integration Layer
FastAPI app principal — v2.1.0
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Routers originais
# Painel
# AI Layer
from app.api import ai_router, importacao, jobs, painel, resultados

# Cadastros
from app.api.cadastros import congenere, empresa, importacao_inicial, segurado

# Corretagem
from app.api.corretagem import corretagem
from app.api.cosseguro import cosseguro

# Emissão
from app.api.emissao import (
    apolice,
    config_apolice,
    consulta_apolice,
    criticas_router,
    faturamento,
    importacao_movimentacao,
    importacao_vidas,
    proposta,
)
from app.api.emissao.criticas_router import router_util as criticas_util_router
from app.api.emissao.faturamento import router_ipca as ipca_router
from app.api.emissao.importacao_movimentacao import (
    router_templates as mov_templates_router,
)

# Operações
from app.api.impressao import controle
from app.api.pessoas import pessoas

# Portal (sem auth — uso do Portal do Corretor)
from app.api.portal import estipulante as portal_estipulante
from app.api.portal import dashboard as portal_dashboard

# Sinistro
from app.api.sinistro import kit_ecm, sinistro

# Auth Layer
from app.auth import router as auth_router

# ── OpenTelemetry (setup antes do app para instrumentação automática) ─────────
from app.core.config import settings
from app.core.telemetry import inject_trace_context, setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LifeCore-Mainframe Integration Layer",
    description=(
        "Ponte entre o front-end e o Legacy Core COBOL (z/OS). "
        "Recebe dados, converte para layout fixo e dispara o ciclo batch. "
        "Módulos: Cadastros · Emissão · Faturamento · Endossos · Coberturas · "
        "Sinistro · Cosseguro · Impressão · Pessoas · Painel · Corretagem · Auth · AI."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restringir em produção
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ── Middleware de correlação — injeta X-Trace-Id em toda resposta ─────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """
    1. Lê X-Request-Id do cliente (ou gera um novo).
    2. Injeta trace_id OTel como header X-Trace-Id na resposta.
    3. Loga método + path + status + trace_id para correlação com logs COBOL.
    """
    import uuid

    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

    response = await call_next(request)

    ctx = inject_trace_context(request_id)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Trace-Id"] = ctx["trace_id"]

    logger.info(
        "method=%s path=%s status=%s trace_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        ctx["trace_id"],
    )
    return response


# ── Ativa OTel depois que o app foi criado ────────────────────────────────────
setup_tracing(app)

# ── Legado (importação e batch) ───────────────────────────────────────────────
app.include_router(importacao.router, prefix="/api/apolices", tags=["Importação"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs Batch"])
app.include_router(resultados.router, prefix="/api/apolices", tags=["Resultados"])

# ── Cadastros ─────────────────────────────────────────────────────────────────
app.include_router(
    empresa.router, prefix="/api/cadastros/empresas", tags=["Cadastros · Empresas"]
)
app.include_router(
    importacao_inicial.router,
    prefix="/api/cadastros/importacoes-iniciais",
    tags=["Cadastros · Importação Inicial"],
)
app.include_router(
    congenere.router,
    prefix="/api/cadastros/congeneres",
    tags=["Cadastros · Congêneres"],
)
app.include_router(
    segurado.router, prefix="/api/cadastros/segurados", tags=["Cadastros · Segurados"]
)

# ── Emissão ───────────────────────────────────────────────────────────────────
app.include_router(
    proposta.router, prefix="/api/emissao/propostas", tags=["Emissão · Propostas"]
)
app.include_router(
    apolice.router, prefix="/api/emissao/apolices", tags=["Emissão · Apólices"]
)
app.include_router(
    config_apolice.router,
    prefix="/api/emissao/apolices/{nr_apolice}",
    tags=["Emissão · Config Apólice"],
)
app.include_router(
    faturamento.router,
    prefix="/api/emissao/apolices",
    tags=["Faturamento · Endossos", "Faturamento · Faturas"],
)
app.include_router(
    consulta_apolice.router,
    prefix="/api/emissao/apolices",
    tags=["Consulta Apólice", "Consulta Apólice · Coberturas"],
)
app.include_router(
    ipca_router, prefix="/api/emissao/taxas-ipca", tags=["Faturamento · IPCA"]
)
app.include_router(
    importacao_movimentacao.router,
    prefix="/api/emissao/apolices",
    tags=["Movimentação · Importação"],
)
app.include_router(
    mov_templates_router, prefix="/api/emissao", tags=["Movimentação · Importação"]
)
app.include_router(
    importacao_vidas.router,
    prefix="/api/emissao/apolices",
    tags=["Movimentação · Importação"],
)
app.include_router(
    criticas_router.router,
    prefix="/api/emissao/apolices",
    tags=["Críticas · Liberação Manual"],
)
app.include_router(
    criticas_util_router,
    prefix="/api/emissao",
    tags=["Críticas · Catálogo", "Críticas · Validação CPF"],
)

# ── Sinistro ──────────────────────────────────────────────────────────────────
app.include_router(sinistro.router, prefix="/api/sinistro", tags=["Sinistro"])
app.include_router(kit_ecm.router, prefix="/api/sinistro", tags=["Sinistro · ECM"])

# ── Operações ─────────────────────────────────────────────────────────────────
app.include_router(
    controle.router, prefix="/api/impressao/controle", tags=["Impressão"]
)
app.include_router(
    cosseguro.router, prefix="/api/cosseguro/participacoes", tags=["Cosseguro"]
)
app.include_router(pessoas.router, prefix="/api/pessoas", tags=["Pessoas"])

# ── Painel ────────────────────────────────────────────────────────────────────
app.include_router(painel.router, prefix="/api/painel", tags=["Painel Interativo"])

# ── Corretagem ────────────────────────────────────────────────────────────────
app.include_router(corretagem.router, prefix="/api/corretagem", tags=["Corretagem"])

# ── Portal do Corretor (sem auth) ────────────────────────────────────────────
app.include_router(
    portal_estipulante.router,
    prefix="/api/portal/estipulantes",
    tags=["Portal · Estipulantes"],
)
app.include_router(
    portal_dashboard.router,
    prefix="/api/portal/dashboard",
    tags=["Portal · Dashboard"],
)

# ── Auth Layer ────────────────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/auth", tags=["Autenticação"])

# ── AI Layer ──────────────────────────────────────────────────────────────────
app.include_router(ai_router.router, prefix="/api/ai", tags=["AI Layer"])

# ── Next.js static export — servido em /app ──────────────────────────────────
# Aponta para frontend/out/ relativo ao repo. Ajuste FRONTEND_BUILD_DIR no
# .env se o build for gerado em outro local.
_FRONTEND_BUILD_DIR = Path(settings.frontend_build_dir)
if _FRONTEND_BUILD_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(_FRONTEND_BUILD_DIR), html=True), name="frontend")
    logger.info("Next.js static export montado em /app ← %s", _FRONTEND_BUILD_DIR)
else:
    logger.warning(
        "FRONTEND_BUILD_DIR não encontrado (%s). "
        "Execute 'npm run build' dentro de frontend/ para gerar o build.",
        _FRONTEND_BUILD_DIR,
    )


@app.get("/", include_in_schema=False)
def root():
    """Redireciona raiz para o frontend Next.js."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/app/")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "servico": "LifeCore Integration Layer", "version": "2.1.0"}
