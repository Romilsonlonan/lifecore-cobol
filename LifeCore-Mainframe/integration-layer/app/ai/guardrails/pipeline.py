"""
LifeCore AI Layer — Guardrails + AI Security
Valida inputs/outputs do agente antes de executar ações.

Camadas de proteção:
  1. Input Guardrail  — sanitiza e valida a pergunta do usuário
  2. Action Guardrail — bloqueia ações destrutivas sem aprovação
  3. Output Guardrail — remove dados sensíveis (PAN, CPF) da resposta
  4. Rate Limiter     — limita chamadas por usuário/minuto

Padrões detectados:
  - Prompt injection (tentativas de "ignore as instruções anteriores")
  - PAN exposure (números de cartão na resposta)
  - SQL injection via tool calling
  - Execução de jobs destrutivos sem aprovação explícita
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Tipos ─────────────────────────────────────────────────────────────────────


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    sanitized: str | None = None  # texto sanitizado (output guardrail)
    risk_score: float = 0.0  # 0.0 = seguro, 1.0 = bloqueado


# ── Padrões de detecção ───────────────────────────────────────────────────────

# Prompt injection — tenta subverter o system prompt
_INJECTION_PATTERNS = [
    r"ignore\s+(as\s+)?instru[cç][oõ]es\s+anteriores",
    r"forget\s+(your\s+)?instructions",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(a\s+)?(?!lifecore)",  # "act as [algo diferente de lifecore]"
    r"jailbreak",
    r"DAN\s+mode",
    r"<\|.*?\|>",  # tokens especiais de modelos
    r"\[SYSTEM\]",
    r"ignore\s+previous",
]

# PAN — número de cartão (16 dígitos, com ou sem separadores)
_PAN_PATTERN = re.compile(
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"  # Visa
    r"5[1-5][0-9]{14}|"  # Mastercard
    r"3[47][0-9]{13}|"  # Amex
    r"3(?:0[0-5]|[68][0-9])[0-9]{11}|"  # Diners
    r"6(?:011|5[0-9]{2})[0-9]{12}|"  # Discover
    r"(?:2131|1800|35\d{3})\d{11})\b"  # JCB
)

# CPF completo (11 dígitos consecutivos)
_CPF_PATTERN = re.compile(r"\b\d{11}\b")

# SQL potencialmente destrutivo
_DESTRUCTIVE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

# Jobs que requerem aprovação explícita
_JOBS_DESTRUTIVOS = {"FATURA01", "PAGTO01", "CONCIL01", "COMIS01", "SETTLE01"}


# ── Input Guardrail ───────────────────────────────────────────────────────────


class InputGuardrail:
    """Valida e sanitiza a entrada do usuário antes de enviar ao LLM."""

    def __init__(self, max_length: int = 2000):
        self._max_length = max_length
        self._compiled = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

    def check(self, text: str) -> GuardrailResult:
        # Comprimento máximo
        if len(text) > self._max_length:
            return GuardrailResult(
                allowed=False,
                reason=f"Mensagem muito longa ({len(text)} chars, máx {self._max_length}).",
                risk_score=0.3,
            )

        # Prompt injection
        for pattern in self._compiled:
            if pattern.search(text):
                logger.warning("Prompt injection detectado: %s", text[:100])
                return GuardrailResult(
                    allowed=False,
                    reason="Tentativa de prompt injection detectada.",
                    risk_score=1.0,
                )

        # SQL destrutivo embutido na pergunta
        if _DESTRUCTIVE_SQL.search(text):
            logger.warning("SQL potencialmente destrutivo na entrada: %s", text[:100])
            return GuardrailResult(
                allowed=False,
                reason="Comandos SQL de escrita não são permitidos via chat.",
                risk_score=0.8,
            )

        return GuardrailResult(allowed=True, risk_score=0.0)


# ── Action Guardrail ──────────────────────────────────────────────────────────


class ActionGuardrail:
    """Valida chamadas de tool antes de executar."""

    def check_tool_call(self, tool_name: str, args: dict) -> GuardrailResult:
        # Job destrutivo sem aprovação
        if tool_name == "disparar_job_cobol":
            job = args.get("nome_job", "")
            aprovado = args.get("aprovado_pelo_usuario", False)
            if job in _JOBS_DESTRUTIVOS and not aprovado:
                return GuardrailResult(
                    allowed=False,
                    reason=(
                        f"O job {job} modifica dados de produção. "
                        "Confirme com o usuário antes de executar."
                    ),
                    risk_score=0.9,
                )

        # SQL destrutivo via tool
        if tool_name == "consultar_banco":
            sql = args.get("sql", "")
            if _DESTRUCTIVE_SQL.search(sql):
                return GuardrailResult(
                    allowed=False,
                    reason=f"SQL destrutivo bloqueado: {sql[:80]}",
                    risk_score=1.0,
                )

        return GuardrailResult(allowed=True, risk_score=0.0)


# ── Output Guardrail ──────────────────────────────────────────────────────────


class OutputGuardrail:
    """Sanitiza a saída do LLM antes de entregar ao usuário."""

    def sanitize(self, text: str) -> GuardrailResult:
        original = text
        risk = 0.0

        # Remove PAN completo — substitui por token mascarado
        pans = _PAN_PATTERN.findall(text)
        if pans:
            for pan in pans:
                masked = pan[:6] + "******" + pan[-4:]
                text = text.replace(pan, masked)
            logger.warning("PAN detectado e mascarado na saída. Count: %d", len(pans))
            risk = max(risk, 0.8)

        # CPF — mantém apenas primeiros 3 e últimos 2 dígitos
        cpfs = _CPF_PATTERN.findall(text)
        for cpf in cpfs:
            if cpf != "0" * 11:  # ignora zeros (placeholders)
                masked = cpf[:3] + ".***.***-" + cpf[-2:]
                text = text.replace(cpf, masked)
        if cpfs:
            risk = max(risk, 0.4)

        return GuardrailResult(
            allowed=True,
            sanitized=text,
            risk_score=risk,
            reason="PAN/CPF mascarados." if risk > 0 else None,
        )


# ── Rate Limiter ──────────────────────────────────────────────────────────────


class RateLimiter:
    """Limita chamadas ao agente por usuário/minuto."""

    def __init__(self, max_per_minute: int = 20):
        self._max = max_per_minute
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> GuardrailResult:
        now = time.time()
        window = now - 60  # último minuto
        history = [t for t in self._calls[user_id] if t > window]
        history.append(now)
        self._calls[user_id] = history

        if len(history) > self._max:
            return GuardrailResult(
                allowed=False,
                reason=f"Rate limit excedido: {len(history)} chamadas/min (máx {self._max}).",
                risk_score=0.5,
            )
        return GuardrailResult(allowed=True, risk_score=0.0)


# ── Pipeline completo ─────────────────────────────────────────────────────────


class GuardrailPipeline:
    """
    Pipeline que encadeia todos os guardrails.

    Uso:
        pipeline = GuardrailPipeline()
        result = pipeline.check_input("usuário1", mensagem)
        if not result.allowed:
            return {"erro": result.reason}

        # executa agente...
        resposta = agente.run(mensagem)

        safe = pipeline.sanitize_output(resposta.answer)
        return {"resposta": safe.sanitized}
    """

    def __init__(self):
        self.input_guard = InputGuardrail()
        self.action_guard = ActionGuardrail()
        self.output_guard = OutputGuardrail()
        self.rate_limiter = RateLimiter()

    def check_input(self, user_id: str, text: str) -> GuardrailResult:
        rl = self.rate_limiter.check(user_id)
        if not rl.allowed:
            return rl
        return self.input_guard.check(text)

    def check_tool_call(self, tool_name: str, args: dict) -> GuardrailResult:
        return self.action_guard.check_tool_call(tool_name, args)

    def sanitize_output(self, text: str) -> GuardrailResult:
        return self.output_guard.sanitize(text)


# ── Singleton ─────────────────────────────────────────────────────────────────
_pipeline: GuardrailPipeline | None = None


def get_guardrails() -> GuardrailPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = GuardrailPipeline()
    return _pipeline
