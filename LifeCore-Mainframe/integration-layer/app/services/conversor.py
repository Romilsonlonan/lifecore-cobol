"""
Conversor de arquivo do corretor → layout de largura fixa CPYAPOL (300 bytes).

Suporta:
  • CSV  (separador vírgula ou ponto-e-vírgula)
  • XLSX (primeira planilha)
  • JSON (lista de objetos)

O layout de saída espelha exatamente COPYLIB/CPYAPOL.cpy:
  Pos  1- 2  : Tipo registro  (D1)
  Pos  3-14  : Número apólice
  Pos 15-17  : Produto (VGC/GLB)
  Pos 18-31  : CNPJ estipulante
  Pos 32-42  : CPF segurado
  Pos 43-82  : Nome segurado  (40 chars)
  Pos 83-90  : Vigência início AAAAMMDD
  Pos 91-98  : Vigência fim    AAAAMMDD
  Pos 99-100 : Status (AT)
  Pos 101    : Tipo capital (F/E/M/B/P)
  Pos 102-115: Capital segurado   COMP-3 emulado como dígitos (13V2 = 15 chars zerofill)
  Pos 116-128: Salário base       (13 chars zerofill)
  Pos 129-134: Fator multiplicador (5V2 = 6 chars)
  Pos 135-148: Prêmio líquido     (13 chars zerofill)
  Pos 149-162: Prêmio bruto       (13 chars zerofill)
  Pos 163-173: IOF                (11 chars zerofill)
  Pos 174-175: Forma pagamento
  Pos 176-177: Periodicidade
  Pos 178-185: Data emissão AAAAMMDD
  Pos 186-193: Usuário inclusão
  Pos 194-219: Timestamp (26 chars)
  Pos 220-300: Filler (espaços)
"""
from __future__ import annotations

import csv
import io
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.schemas.apolice import ApoliceInput


# Tamanho total do registro (bytes)
RECORD_SIZE = 300


def _fmt_str(value: str, length: int) -> str:
    """Trunca ou preenche com espaços à direita."""
    return str(value or "").ljust(length)[:length]


def _fmt_num(value: float | None, total_digits: int) -> str:
    """Converte float para string numérica zerofilled sem separador decimal."""
    if value is None:
        return "0" * total_digits
    # Multiplica por 100 para incluir 2 casas decimais implícitas (V99 COMP-3)
    intval = int(round(value * 100))
    return str(intval).zfill(total_digits)


def apolice_to_fixed(apolice: ApoliceInput, seq: int) -> str:
    """Converte um objeto ApoliceInput para uma linha de 300 chars."""
    now = datetime.now(timezone.utc)
    linha = (
        "D1"                                                     # pos 1-2
        + _fmt_str(apolice.numero_apolice, 12)                   # pos 3-14
        + _fmt_str(apolice.produto.value, 3)                     # pos 15-17
        + _fmt_str(apolice.cnpj_estipulante, 14)                 # pos 18-31
        + _fmt_str(apolice.cpf_segurado, 11)                     # pos 32-42
        + _fmt_str(apolice.nome_segurado, 40)                    # pos 43-82
        + _fmt_str(apolice.vigencia_ini, 8)                      # pos 83-90
        + _fmt_str(apolice.vigencia_fim, 8)                      # pos 91-98
        + "AT"                                                   # pos 99-100
        + _fmt_str(apolice.tipo_capital.value, 1)                # pos 101
        + _fmt_num(apolice.capital_segurado, 15)                 # pos 102-116
        + _fmt_num(apolice.salario_base, 13)                     # pos 117-129
        + _fmt_num(apolice.fator_multiplicador, 6)               # pos 130-135
        + _fmt_num(apolice.premio_liquido, 14)                   # pos 136-149
        + _fmt_num(apolice.premio_bruto, 14)                     # pos 150-163
        + _fmt_num(apolice.iof, 12)                              # pos 164-175
        + _fmt_str(apolice.forma_pagamento.value, 2)             # pos 176-177
        + _fmt_str(apolice.periodicidade.value, 2)               # pos 178-179
        + now.strftime("%Y%m%d")                                 # pos 180-187
        + "APIUSER "                                             # pos 188-195
        + now.strftime("%Y-%m-%dT%H:%M:%S.000000")              # pos 196-221
    )
    # Preenche com espaços até 300 chars
    linha = linha.ljust(RECORD_SIZE)[:RECORD_SIZE]
    return linha


def build_flat_file(apolices: list[ApoliceInput]) -> str:
    """
    Monta o arquivo flat completo com header H0 + detalhes D1 + trailer T9.
    Retorna o conteúdo como string (uma linha por registro).
    """
    header  = ("H0" + " " * (RECORD_SIZE - 2))[:RECORD_SIZE]
    trailer = ("T9" + str(len(apolices)).zfill(7) + " " * RECORD_SIZE)[:RECORD_SIZE]
    lines = [header]
    for i, apolice in enumerate(apolices, start=1):
        lines.append(apolice_to_fixed(apolice, i))
    lines.append(trailer)
    return "\n".join(lines) + "\n"


# ── Parsers de arquivo ─────────────────────────────────────────────────────

_CSV_CAMPOS = [
    "numero_apolice", "produto", "cnpj_estipulante", "cpf_segurado",
    "nome_segurado", "vigencia_ini", "vigencia_fim", "tipo_capital",
    "capital_segurado", "salario_base", "fator_multiplicador",
    "premio_liquido", "premio_bruto", "iof", "forma_pagamento", "periodicidade",
]


def _row_to_apolice(row: dict) -> ApoliceInput:
    """Converte um dicionário (linha CSV/XLSX) para ApoliceInput."""
    def _float(v):
        """Converte para float; retorna None se vazio/zero."""
        if v in (None, "", "0", 0):
            return None
        try:
            return float(str(v).strip())
        except (ValueError, TypeError):
            return None

    def _req_float(v, field: str) -> float:
        """Float obrigatório; lança ValueError claro se inválido."""
        if v in (None, ""):
            return 0.0          # default seguro — ARQVAL01 vai rejeitar capital=0
        try:
            return float(str(v).strip())
        except (ValueError, TypeError):
            raise ValueError(f"Valor inválido para '{field}': {v!r}")

    return ApoliceInput(
        numero_apolice      = str(row["numero_apolice"]).strip(),
        produto             = str(row["produto"]).strip().upper(),
        cnpj_estipulante    = str(row["cnpj_estipulante"]).strip().replace(".", "").replace("/", "").replace("-", ""),
        cpf_segurado        = str(row["cpf_segurado"]).strip().replace(".", "").replace("-", ""),
        nome_segurado       = str(row["nome_segurado"]).strip(),
        vigencia_ini        = str(row["vigencia_ini"]).strip().replace("-", ""),
        vigencia_fim        = str(row["vigencia_fim"]).strip().replace("-", ""),
        tipo_capital        = str(row["tipo_capital"]).strip().upper(),
        capital_segurado    = _req_float(row.get("capital_segurado"), "capital_segurado"),
        salario_base        = _float(row.get("salario_base")),
        fator_multiplicador = _float(row.get("fator_multiplicador")),
        premio_liquido      = _req_float(row.get("premio_liquido"), "premio_liquido"),
        premio_bruto        = _req_float(row.get("premio_bruto"), "premio_bruto"),
        iof                 = _float(row.get("iof")),
        forma_pagamento     = str(row.get("forma_pagamento", "BO")).strip().upper() or "BO",
        periodicidade       = str(row.get("periodicidade", "MN")).strip().upper() or "MN",
    )


def parse_csv(content: bytes) -> list[ApoliceInput]:
    """Parseia CSV (vírgula ou ponto-e-vírgula)."""
    text = content.decode("utf-8-sig")
    # Detecta separador
    sep = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    return [_row_to_apolice(row) for row in reader]


def parse_xlsx(content: bytes) -> list[ApoliceInput]:
    """Parseia XLSX (primeira planilha)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(c).strip().lower().replace(" ", "_") for c in rows[0]]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        d = dict(zip(header, row))
        result.append(_row_to_apolice(d))
    return result


def parse_json(content: bytes) -> list[ApoliceInput]:
    """Parseia JSON (array de objetos)."""
    data = json.loads(content.decode("utf-8"))
    return [ApoliceInput(**item) for item in data]


def parse_arquivo(filename: str, content: bytes) -> list[ApoliceInput]:
    """Despacha para o parser correto baseado na extensão."""
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return parse_csv(content)
    elif ext in (".xlsx", ".xls"):
        return parse_xlsx(content)
    elif ext == ".json":
        return parse_json(content)
    else:
        raise ValueError(f"Formato não suportado: {ext}. Use .csv, .xlsx ou .json")
