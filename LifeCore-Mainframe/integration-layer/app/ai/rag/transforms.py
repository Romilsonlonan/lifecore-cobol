"""
LifeCore AI Layer — Transform Pipeline
Pré-processa texto por tipo de arquivo antes da geração de embeddings.

Cada Transform recebe texto bruto e devolve texto limpo e normalizado.
O Indexer (engine.py) aplica automaticamente o transform correto
com base na extensão do arquivo (FILE_TYPES).

Transforms disponíveis:
  CobolTransform   — remove colunas de sequência, preserva lógica
  JclTransform     — extrai steps/programas, remove comentários
  CopybookTransform— foca em nomes de campos e seus formatos PIC
  SqlTransform     — remove comentários, normaliza DDL
  MarkdownTransform— remove fences de código, preserva estrutura
  AbendTransform   — extrai abend code, programa e step (dumps)
  PythonTransform  — remove docstrings longas, preserva assinaturas
  NullTransform    — passthrough sem modificação (fallback)
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

# ── Interface base ─────────────────────────────────────────────────────────────

class BaseTransform(ABC):
    """Contrato de todos os transforms."""

    @abstractmethod
    def __call__(self, text: str) -> str:
        """Recebe texto bruto, devolve texto processado."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ── Transforms por tipo de arquivo ────────────────────────────────────────────

class NullTransform(BaseTransform):
    """Passthrough — sem modificação. Usado como fallback."""

    def __call__(self, text: str) -> str:
        return text


class CobolTransform(BaseTransform):
    """
    Pré-processa fonte COBOL para embedding semântico.

    Remove:
      - Colunas de sequência (1-6) e área de identificação (73-80)
      - Linhas de comentário (*> e * na col 7)
      - Linhas em branco consecutivas (reduz a 1)
    Preserva:
      - DIVISION / SECTION / PARAGRAPH headers
      - Nomes de variáveis e suas cláusulas PIC/COMP
      - Verbos COBOL (MOVE, PERFORM, IF, EVALUATE…)
    """

    # Linhas de comentário COBOL: asterisco na coluna 7 (índice 6)
    _COMMENT = re.compile(r"^.{0,6}\*.*$", re.MULTILINE)
    # Inline comment moderno (*>)
    _INLINE_COMMENT = re.compile(r"\*>.*$", re.MULTILINE)
    # Colunas 1-6 e 73-80 (sequência e identificação)
    _SEQ_COLS = re.compile(r"^(.{6})(.{0,66})(.{0,8})$", re.MULTILINE)
    # Múltiplas linhas em branco
    _BLANK_LINES = re.compile(r"\n{3,}")

    def __call__(self, text: str) -> str:
        # Remove colunas 1-6 e 73-80, mantém cols 7-72
        lines = []
        for line in text.splitlines():
            core = line[6:72] if len(line) > 6 else line
            lines.append(core)
        text = "\n".join(lines)

        text = self._COMMENT.sub("", text)
        text = self._INLINE_COMMENT.sub("", text)
        text = self._BLANK_LINES.sub("\n\n", text)
        return text.strip()


class CopybookTransform(BaseTransform):
    """
    Extrai informação semântica de copybooks COBOL.

    Foca em: nomes de campos (01/05/10…), PIC clause, COMP/COMP-3,
    REDEFINES e VALUES — descartando ruído estrutural.
    """

    _LEVEL_LINE = re.compile(
        r"^\s*(\d{2})\s+([\w-]+)\s*(.*?)[\.\s]*$", re.MULTILINE
    )
    _COMMENT = re.compile(r"^.{0,6}\*.*$", re.MULTILINE)

    def __call__(self, text: str) -> str:
        # Remove comentários
        text = self._COMMENT.sub("", text)

        # Extrai linhas de definição de campos
        entries = []
        for m in self._LEVEL_LINE.finditer(text):
            level, name, clause = m.group(1), m.group(2), m.group(3).strip()
            indent = "  " * (int(level) // 5)
            entries.append(f"{indent}{level} {name} {clause}".rstrip())

        return "\n".join(entries) if entries else text.strip()


class JclTransform(BaseTransform):
    """
    Normaliza JCL para embedding semântico.

    Extrai:
      - Nome do JOB e parâmetros CLASS/MSGCLASS
      - Cada STEP: nome, EXEC PGM= ou PROC=
      - DD statements relevantes (DSN, DISP)
    Remove:
      - Linhas de comentário (//* )
      - Continuações de linha redundantes
    """

    _COMMENT = re.compile(r"^//\*.*$", re.MULTILINE)
    _BLANK = re.compile(r"\n{3,}")
    # Captura STEP e programa/proc
    _EXEC = re.compile(r"^//(\w+)\s+EXEC\s+(PGM=\w+|PROC=\w+|\w+)", re.MULTILINE)
    _JOB  = re.compile(r"^//(\w+)\s+JOB\b", re.MULTILINE)

    def __call__(self, text: str) -> str:
        text = self._COMMENT.sub("", text)
        text = self._BLANK.sub("\n\n", text)
        return text.strip()


class SqlTransform(BaseTransform):
    """
    Normaliza SQL/DDL para embedding semântico.

    Remove:
      - Comentários de linha (--)
      - Comentários de bloco (/* … */)
      - Espaços e newlines redundantes
    Normaliza palavras-chave para maiúsculas.
    """

    _LINE_COMMENT  = re.compile(r"--[^\n]*")
    _BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
    _EXCESS_WS     = re.compile(r"[ \t]{2,}")
    _BLANK         = re.compile(r"\n{3,}")

    _KEYWORDS = [
        "select", "from", "where", "insert", "into", "update", "delete",
        "create", "table", "alter", "drop", "index", "primary", "foreign",
        "references", "constraint", "not", "null", "default", "unique",
    ]

    def __call__(self, text: str) -> str:
        text = self._BLOCK_COMMENT.sub("", text)
        text = self._LINE_COMMENT.sub("", text)
        text = self._EXCESS_WS.sub(" ", text)
        text = self._BLANK.sub("\n\n", text)
        for kw in self._KEYWORDS:
            text = re.sub(rf"\b{kw}\b", kw.upper(), text, flags=re.IGNORECASE)
        return text.strip()


class MarkdownTransform(BaseTransform):
    """
    Processa Markdown (AGENTS.md, RUNBOOK, DOCS.md).

    Remove fences de código (preserva o conteúdo dentro delas, que
    pode ser JCL ou SQL relevante), colapsa espaços extras.
    """

    _FENCE = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)
    _BLANK = re.compile(r"\n{4,}")

    def __call__(self, text: str) -> str:
        # Preserva conteúdo dentro de fences mas remove os marcadores
        text = self._FENCE.sub(lambda m: m.group(1), text)
        text = self._BLANK.sub("\n\n\n", text)
        return text.strip()


class AbendTransform(BaseTransform):
    """
    Extrai informação estruturada de logs/dumps de abend.

    Identifica e rotula: código de abend, programa, step, SQLCODE,
    offset de instrução — facilita a recuperação semântica pelo
    agente 🛠️ Sustentação (LCIQ-SUS-*).
    """

    _ABEND   = re.compile(r"\b(S[0-9A-F]{3}|U\d{4})\b")
    _SQLCODE = re.compile(r"SQLCODE[=\s]+(-?\d+)")
    _PROGRAM = re.compile(r"(?:PROGRAM|PGM)[=\s:]+(\w+)")
    _STEP    = re.compile(r"STEP\s*[=:\s]+(\w+)")

    def __call__(self, text: str) -> str:
        # Extrai tags estruturadas no topo para melhorar retrieval
        tags: list[str] = []
        for m in self._ABEND.finditer(text):
            tags.append(f"[ABEND:{m.group(1)}]")
        for m in self._SQLCODE.finditer(text):
            tags.append(f"[SQLCODE:{m.group(1)}]")
        for m in self._PROGRAM.finditer(text):
            tags.append(f"[PGM:{m.group(1)}]")
        for m in self._STEP.finditer(text):
            tags.append(f"[STEP:{m.group(1)}]")

        prefix = " ".join(dict.fromkeys(tags))  # deduplica mantendo ordem
        return (f"{prefix}\n\n{text}" if prefix else text).strip()


class PythonTransform(BaseTransform):
    """
    Processa fontes Python (services, api, ai layer).

    Remove docstrings longas (> 10 linhas) mas preserva a primeira linha
    de cada docstring como resumo. Mantém assinaturas de função/classe
    e comentários inline curtos.
    """

    _DOCSTRING = re.compile(r'"""(.*?)"""', re.DOTALL)

    def __call__(self, text: str) -> str:
        def shorten(m: re.Match) -> str:
            content = m.group(1).strip()
            first_line = content.splitlines()[0].strip()
            lines = content.splitlines()
            if len(lines) > 10:
                return f'"""{first_line}"""'
            return m.group(0)

        return self._DOCSTRING.sub(shorten, text).strip()


# ── Registro: extensão → transform ────────────────────────────────────────────

TRANSFORM_REGISTRY: dict[str, BaseTransform] = {
    ".cbl": CobolTransform(),
    ".cpy": CopybookTransform(),
    ".jcl": JclTransform(),
    ".sql": SqlTransform(),
    ".md":  MarkdownTransform(),
    ".py":  PythonTransform(),
}

_NULL = NullTransform()


def get_transform(file_extension: str) -> BaseTransform:
    """Retorna o transform adequado para a extensão informada."""
    return TRANSFORM_REGISTRY.get(file_extension.lower(), _NULL)
