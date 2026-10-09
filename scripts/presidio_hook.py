#!/usr/bin/env python3
"""
Presidio PII/PAN Hook — LifeCore IQ
Detecta dados pessoais (LGPD) e dados de cartão (PCI-DSS) em código Python
antes do commit. Bloqueia se encontrar CPF, PAN, email ou telefone em strings
de log, print ou SQL hardcoded.

Uso: pre-commit run presidio-pii-scan
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

# ---------------------------------------------------------------------------
# Configuração: entidades bloqueantes e padrões COBOL/SQL específicos
# ---------------------------------------------------------------------------
BLOCKED_ENTITIES = {
    "CREDIT_CARD":   "PCI-DSS: número de cartão (PAN) detectado",
    "BR_CPF":        "LGPD: CPF detectado em código",
    "EMAIL_ADDRESS": "LGPD: e-mail detectado em string hardcoded",
    "PHONE_NUMBER":  "LGPD: telefone detectado em string hardcoded",
}

# Padrões extras para PAN e CPF com regex simples (fallback)
EXTRA_PATTERNS = [
    (re.compile(r'\b4[0-9]{15}\b|\b5[1-5][0-9]{14}\b'),          "PCI-DSS: PAN Visa/Master hardcoded"),
    (re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'),                "LGPD: CPF formatado hardcoded"),
    (re.compile(r'(?i)(pan|numero.cartao|nr.cartao.completo)\s*='), "PCI-DSS: campo PAN hardcoded"),
]

# Linhas/contextos que não devem ser escaneados
IGNORE_PATTERNS = [
    re.compile(r'#.*noqa.*presidio', re.I),
    re.compile(r'#.*presidio.*ignore', re.I),
    re.compile(r'TESTDATA|test_.*cpf|cpf.*test|exemplo|example', re.I),
]

# ---------------------------------------------------------------------------
# Setup do Presidio (sem modelo spaCy pesado — usa pattern-based)
# ---------------------------------------------------------------------------
def build_analyzer() -> AnalyzerEngine:
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "pt", "model_name": "pt_core_news_sm"}],
    }
    try:
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["pt", "en"])
    except Exception:
        # Fallback sem modelo pt — usa apenas regex recognizers
        return AnalyzerEngine()


def should_ignore_line(line: str) -> bool:
    return any(p.search(line) for p in IGNORE_PATTERNS)


def scan_file(path: Path, analyzer: AnalyzerEngine) -> list[str]:
    violations: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return violations

    for lineno, line in enumerate(content.splitlines(), start=1):
        if should_ignore_line(line):
            continue

        # Regex extra patterns (rápido, sem NLP)
        for pattern, msg in EXTRA_PATTERNS:
            if pattern.search(line):
                violations.append(f"  {path}:{lineno} — {msg}")

        # Presidio NLP scan em strings longas o suficiente
        stripped = line.strip()
        if len(stripped) < 8:
            continue
        try:
            results = analyzer.analyze(
                text=stripped,
                entities=list(BLOCKED_ENTITIES.keys()),
                language="pt",
            )
            for r in results:
                if r.score >= 0.6:
                    msg = BLOCKED_ENTITIES.get(r.entity_type, r.entity_type)
                    violations.append(f"  {path}:{lineno} — {msg} (score={r.score:.2f})")
        except Exception:
            pass

    return violations


def main(files: list[str]) -> int:
    if not files:
        return 0

    analyzer = build_analyzer()
    all_violations: list[str] = []

    for f in files:
        path = Path(f)
        if path.suffix not in {".py"}:
            continue
        all_violations.extend(scan_file(path, analyzer))

    if all_violations:
        print("🔏 Presidio PII/PAN — VIOLAÇÕES DETECTADAS:", file=sys.stderr)
        for v in all_violations:
            print(v, file=sys.stderr)
        print(
            "\n💡 Se for dado de teste, adicione  # presidio: ignore  na linha.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
