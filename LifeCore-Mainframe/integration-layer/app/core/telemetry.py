"""
LifeCore-Mainframe — OpenTelemetry
Configura tracing distribuído para a Integration Layer FastAPI.

Arquitetura de observabilidade:
  FastAPI → OTLP exporter → Collector → Jaeger / Tempo / DataDog
                                      ↑
  Job COBOL → propaga trace_id no campo TRACE-ID do arquivo de controle

Variáveis de ambiente:
  OTEL_ENABLED        = "true" | "false"  (default: false em dev)
  OTEL_SERVICE_NAME   = "lifecore-integration-layer"
  OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"  (gRPC)
  OTEL_EXPORTER_TYPE  = "grpc" | "http" | "console" (default: console)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Feature flag ──────────────────────────────────────────────────────────────
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "lifecore-integration-layer")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
EXPORTER_TYPE = os.getenv("OTEL_EXPORTER_TYPE", "console")  # console | grpc | http


def setup_tracing(app) -> Optional[object]:
    """
    Instrumenta o app FastAPI com OpenTelemetry.
    Retorna o TracerProvider configurado ou None se OTEL_ENABLED=false.

    Como funciona:
      1. Cada request HTTP recebe um span automático com atributos:
         http.method, http.url, http.status_code, http.route
      2. O span_id e trace_id ficam disponíveis para propagação ao COBOL
         via header X-Trace-Id (injetado pelo middleware de correlação).
      3. O exporter envia os spans ao Collector (Jaeger/Grafana Tempo).
    """
    if not OTEL_ENABLED:
        logger.info("OpenTelemetry desabilitado (OTEL_ENABLED=false).")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({
            "service.name":      SERVICE_NAME,
            "service.version":   "2.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })

        provider = TracerProvider(resource=resource)

        # ── Exporter ─────────────────────────────────────────────────────────
        if EXPORTER_TYPE == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
            logger.info("OTel → OTLP gRPC: %s", OTLP_ENDPOINT)

        elif EXPORTER_TYPE == "http":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            http_endpoint = os.getenv(
                "OTEL_EXPORTER_OTLP_HTTP_ENDPOINT",
                "http://localhost:4318/v1/traces",
            )
            exporter = OTLPSpanExporter(endpoint=http_endpoint)
            logger.info("OTel → OTLP HTTP: %s", http_endpoint)

        else:
            # Console — útil em dev para ver os spans no terminal
            exporter = ConsoleSpanExporter()
            logger.info("OTel → Console (dev mode).")

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # ── Instrumentação automática do FastAPI ──────────────────────────────
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="/health,/docs,/redoc,/openapi.json",
        )

        logger.info("OpenTelemetry ativo — service: %s", SERVICE_NAME)
        return provider

    except ImportError as e:
        logger.warning("Dependência OTel ausente: %s. Tracing desabilitado.", e)
        return None


def get_tracer(name: str = SERVICE_NAME):
    """
    Retorna um tracer para criar spans manuais nos handlers.

    Uso nos routers:
        from app.core.telemetry import get_tracer
        tracer = get_tracer(__name__)

        @router.post("/...")
        def criar_proposta(payload: ...):
            with tracer.start_as_current_span("emissao.criar_proposta") as span:
                span.set_attribute("nr_proposta", payload.nr_proposta)
                span.set_attribute("cd_empresa", payload.cd_empresa)
                ...
    """
    if not OTEL_ENABLED:
        # Retorna tracer noop — não quebra o código quando OTel está desabilitado
        from opentelemetry import trace
        return trace.get_tracer(name)

    from opentelemetry import trace
    return trace.get_tracer(name)


def inject_trace_context(job_id: str) -> dict:
    """
    Retorna os headers de propagação W3C TraceContext para injetar
    no arquivo de controle do job COBOL (campo TRACE-ID, 32 bytes).

    O COBOL não lê HTTP headers, mas podemos gravar o trace_id
    no primeiro registro do arquivo de controle do batch.
    O collector então correlaciona os spans FastAPI ↔ logs COBOL.

    Retorno:
        {
          "traceparent": "00-<trace_id>-<span_id>-01",
          "trace_id":    "<trace_id hex 32 chars>",
          "span_id":     "<span_id hex 16 chars>",
          "job_id":      "<job_id>"
        }
    """
    try:
        from opentelemetry import trace
        from opentelemetry.propagate import inject

        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            trace_id = format(ctx.trace_id, "032x")
            span_id  = format(ctx.span_id,  "016x")
            traceparent = f"00-{trace_id}-{span_id}-01"
        else:
            trace_id    = "0" * 32
            span_id     = "0" * 16
            traceparent = ""

        return {
            "traceparent": traceparent,
            "trace_id":    trace_id,
            "span_id":     span_id,
            "job_id":      job_id,
        }

    except Exception:
        return {"traceparent": "", "trace_id": "0" * 32, "span_id": "0" * 16, "job_id": job_id}
