"""Leitura e validação básica de planilhas para cadastro inicial."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

MAX_ROWS = 50_000
MAX_COLUMNS = 100

FIELDS = (
    "subestipulante",
    "modulo",
    "nome_segurado",
    "dt_nascimento",
    "cpf",
    "dt_admissao",
)

ALIASES = {
    "subestipulante": {"sub", "subestipulante", "sub_estipulante", "filial"},
    "modulo": {"modulo", "modulos", "plano", "cobertura"},
    "nome_segurado": {"nome", "nomes", "nome_segurado", "colaborador", "funcionario"},
    "dt_nascimento": {
        "data_de_nascimento",
        "data_nascimento",
        "dt_nascimento",
        "nascimento",
    },
    "cpf": {"cpf", "cpf_segurado", "documento"},
    "dt_admissao": {
        "data_de_admissao",
        "data_admissao",
        "dt_admissao",
        "admissao",
        "dt_inclusao",
    },
}


def _normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def suggested_mapping(headers: list[str]) -> dict[str, int | None]:
    normalized = [_normalize_header(header) for header in headers]
    result: dict[str, int | None] = {}
    for field, aliases in ALIASES.items():
        result[field] = next(
            (index for index, header in enumerate(normalized) if header in aliases),
            None,
        )
    return result


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_csv(content: bytes) -> list[list[Any]]:
    text = content.decode("utf-8-sig")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = max((";", ",", "\t"), key=first_line.count)
    return [list(row) for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _parse_xlsx(content: bytes) -> list[list[Any]]:
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        if sheet is None:
            raise ValueError("A planilha XLSX não contém uma aba ativa.")
        rows: list[list[Any]] = []
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            if index > MAX_ROWS:
                raise ValueError(f"A planilha excede o limite de {MAX_ROWS:,} linhas.")
            rows.append(list(row))
        return rows
    finally:
        workbook.close()


def _parse_xls(content: bytes) -> list[list[Any]]:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
    try:
        sheet = workbook.sheet_by_index(0)
        if sheet.nrows > MAX_ROWS + 1:
            raise ValueError(f"A planilha excede o limite de {MAX_ROWS:,} linhas.")
        rows: list[list[Any]] = []
        for row_index in range(sheet.nrows):
            row: list[Any] = []
            for cell in sheet.row(row_index):
                if cell.ctype == xlrd.XL_CELL_DATE:
                    if not isinstance(cell.value, (int, float)):
                        raise ValueError("A planilha XLS contém uma data inválida.")
                    row.append(
                        xlrd.xldate_as_datetime(float(cell.value), workbook.datemode)
                    )
                else:
                    row.append(cell.value)
            rows.append(row)
        return rows
    finally:
        workbook.release_resources()


def _parse_ods(content: bytes) -> list[list[Any]]:
    from odf import teletype
    from odf.namespaces import TABLENS
    from odf.opendocument import load
    from odf.table import Table, TableRow

    document = load(io.BytesIO(content))
    sheets = document.spreadsheet.getElementsByType(Table)
    if not sheets:
        return []
    rows: list[list[Any]] = []
    for row_node in sheets[0].getElementsByType(TableRow):
        if len(rows) > MAX_ROWS:
            raise ValueError(f"A planilha excede o limite de {MAX_ROWS:,} linhas.")
        values: list[Any] = []
        for cell in row_node.childNodes:
            cell_type = getattr(cell, "qname", None)
            if cell_type not in {
                (TABLENS, "table-cell"),
                (TABLENS, "covered-table-cell"),
            }:
                continue
            attributes = cell.attributes
            value_type = attributes.get("valuetype")
            date_value = attributes.get("datevalue")
            value = (
                ""
                if cell_type == (TABLENS, "covered-table-cell")
                else date_value
                if value_type == "date" and date_value
                else attributes.get("value")
                if value_type in {"float", "currency", "percentage"}
                else teletype.extractText(cell)
            )
            repeat = min(int(attributes.get("numbercolumnsrepeated", 1)), 1000)
            values.extend([value] * repeat)
        rows.append(values)
    return rows


def parse_spreadsheet(filename: str, content: bytes) -> tuple[list[str], list[list[str]]]:
    extension = Path(filename).suffix.lower()
    parsers = {
        ".csv": _parse_csv,
        ".xlsx": _parse_xlsx,
        ".xls": _parse_xls,
        ".ods": _parse_ods,
    }
    parser = parsers.get(extension)
    if parser is None:
        raise ValueError("Formato não suportado. Use CSV, XLSX, XLS ou ODS.")
    rows = parser(content)
    while rows and not any(_value_text(cell) for cell in rows[0]):
        rows.pop(0)
    if not rows:
        raise ValueError("A planilha está vazia.")
    headers = [
        _value_text(cell) or f"Coluna {index + 1}"
        for index, cell in enumerate(rows[0])
    ]
    if len(headers) > MAX_COLUMNS:
        raise ValueError(f"A planilha excede o limite de {MAX_COLUMNS} colunas.")
    if not any(_value_text(value) for value in headers):
        raise ValueError("Não foi possível identificar o cabeçalho da planilha.")
    records = [
        [_value_text(row[index]) if index < len(row) else "" for index in range(len(headers))]
        for row in rows[1:]
        if any(_value_text(cell) for cell in row)
    ]
    if not records:
        raise ValueError("A planilha não contém linhas de dados após o cabeçalho.")
    if len(records) > MAX_ROWS:
        raise ValueError(f"A planilha excede o limite de {MAX_ROWS:,} linhas.")
    return headers, records


def _parse_date(value: str) -> str | None:
    if not value:
        return None
    formats = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y%m%d")
    for fmt in formats:
        try:
            parsed = datetime.strptime(value.strip(), fmt).date()
            return parsed.strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValueError("data inválida (use DD/MM/AAAA ou AAAAMMDD)")


def map_and_validate(
    headers: list[str], records: list[list[str]], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    if set(mapping) != set(FIELDS):
        raise ValueError("O mapeamento deve informar cada campo obrigatório.")
    selected: dict[str, int] = {}
    for field in FIELDS:
        index = mapping[field]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(headers):
            raise ValueError(f"Selecione uma coluna válida para {field}.")
        if re.search(
            r"salari|cargo|capital|remuner",
            _normalize_header(headers[index]),
        ):
            raise ValueError(
                "Salário, cargo e capital são configurados no contrato e não podem ser importados."
            )
        selected[field] = index
    if len(set(selected.values())) != len(selected):
        raise ValueError("Cada campo precisa usar uma coluna diferente.")

    cpf_seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for line_number, cells in enumerate(records, start=2):
        values = {field: cells[index] if index < len(cells) else "" for field, index in selected.items()}
        errors: list[str] = []
        cpf_digits = re.sub(r"\D", "", values["cpf"])
        if cpf_digits and len(cpf_digits) < 11:
            cpf_digits = cpf_digits.zfill(11)
        if len(cpf_digits) != 11:
            errors.append("CPF deve conter 11 dígitos.")
        elif cpf_digits in cpf_seen:
            errors.append("CPF duplicado nesta planilha.")
        else:
            cpf_seen.add(cpf_digits)
        for field, label in (
            ("subestipulante", "subestipulante"),
            ("modulo", "módulo"),
            ("nome_segurado", "nome"),
            ("dt_nascimento", "data de nascimento"),
            ("dt_admissao", "data de admissão"),
        ):
            if not values[field]:
                errors.append(f"Campo {label} obrigatório.")
        try:
            birth_date = _parse_date(values["dt_nascimento"])
        except ValueError as exc:
            birth_date = None
            errors.append(f"Data de nascimento: {exc}.")
        try:
            admission_date = _parse_date(values["dt_admissao"])
        except ValueError as exc:
            admission_date = None
            errors.append(f"Data de admissão: {exc}.")
        if len(values["nome_segurado"]) > 120:
            errors.append("Nome excede 120 caracteres.")
        if len(values["subestipulante"]) > 60:
            errors.append("Subestipulante excede 60 caracteres.")
        if len(values["modulo"]) > 60:
            errors.append("Módulo excede 60 caracteres.")
        output.append(
            {
                "linha_planilha": line_number,
                "subestipulante": values["subestipulante"][:60],
                "modulo": values["modulo"][:60],
                "nome_segurado": values["nome_segurado"][:120],
                "cpf": cpf_digits[:20],
                "dt_nascimento": birth_date,
                "dt_admissao": admission_date,
                "erros": errors,
            }
        )
    return output


def mask_preview_rows(
    headers: list[str], records: list[list[str]], limit: int = 5
) -> list[list[str]]:
    def mask_value(header: str, value: str) -> str:
        normalized = _normalize_header(header)
        if re.search(r"salari|cargo|capital|remuner", normalized):
            return ""
        if value and re.search(r"cpf|documento", normalized):
            return f"***{re.sub(r'\\D', '', value)[-4:]}"
        return value

    return [
        [mask_value(header, value) for header, value in zip(headers, row)]
        for row in records[:limit]
    ]
