from __future__ import annotations

import json
from io import BytesIO

import openpyxl
import pytest
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.cadastros import importacao_inicial as importacao_api
from app.auth.dependencies import get_current_user
from app.repositories.empresa_db2 import Db2Unavailable
from app.services.importacao_inicial import (
    map_and_validate,
    mask_preview_rows,
    parse_spreadsheet,
    suggested_mapping,
)

_api_app = FastAPI()
_api_app.include_router(
    importacao_api.router,
    prefix="/api/cadastros/importacoes-iniciais",
)


SAMPLE_CSV = (
    "Sub;Modulos;Nomes;Data de Nascimento;CPF;Data de Admissao;Salario;Cargos\n"
    "Matriz;VGC;Ana Silva;12/03/1985;1234567890;01/02/2020;5000;Analista\n"
    "Matriz;VGC;Bruno Souza;1980-04-05;52998224725;20200101;6000;Gerente\n"
).encode()

MAPPING = {
    "subestipulante": 0,
    "modulo": 1,
    "nome_segurado": 2,
    "dt_nascimento": 3,
    "cpf": 4,
    "dt_admissao": 5,
}


def test_suggested_mapping_and_semicolon_csv_normalize_headers_and_dates():
    headers, records = parse_spreadsheet("vidas.csv", SAMPLE_CSV)

    assert suggested_mapping(headers) == MAPPING
    rows = map_and_validate(headers, records, MAPPING)

    assert rows[0]["cpf"] == "01234567890"
    assert rows[0]["dt_nascimento"] == "19850312"
    assert rows[0]["dt_admissao"] == "20200201"
    assert rows[0]["erros"] == []
    assert rows[1]["dt_nascimento"] == "19800405"
    assert rows[1]["dt_admissao"] == "20200101"


def test_preview_masks_cpf_and_excludes_salary_and_job_title():
    headers, records = parse_spreadsheet("vidas.csv", SAMPLE_CSV)

    preview = mask_preview_rows(headers, records)

    assert preview[0][4] == "***7890"
    assert preview[0][6:] == ["", ""]


def test_mapping_rejects_salary_job_title_and_capital_columns():
    headers, records = parse_spreadsheet("vidas.csv", SAMPLE_CSV)
    invalid_mapping = {**MAPPING, "dt_admissao": 6}

    with pytest.raises(ValueError, match="Salário, cargo e capital"):
        map_and_validate(headers, records, invalid_mapping)


def test_mapping_marks_duplicate_cpf_and_invalid_dates_for_review():
    headers = ["Sub", "Modulos", "Nomes", "Data de Nascimento", "CPF", "Data de Admissao"]
    records = [
        ["Matriz", "VGC", "Ana Silva", "31/02/1985", "52998224725", "01/01/2020"],
        ["Matriz", "VGC", "Ana Silva", "12/03/1985", "52998224725", "01/01/2020"],
    ]

    rows = map_and_validate(headers, records, MAPPING)

    assert any("Data de nascimento" in error for error in rows[0]["erros"])
    assert any("CPF duplicado" in error for error in rows[1]["erros"])


def test_xlsx_numeric_cpf_with_lost_leading_zero_is_zero_padded():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Sub", "Modulos", "Nomes", "Data de Nascimento", "CPF", "Data de Admissao"])
    sheet.append(["Matriz", "VGC", "Ana Silva", "12/03/1985", 1234567890, "01/02/2020"])
    content = BytesIO()
    workbook.save(content)

    headers, records = parse_spreadsheet("vidas.xlsx", content.getvalue())
    row = map_and_validate(headers, records, MAPPING)[0]

    assert row["cpf"] == "01234567890"
    assert row["erros"] == []


def test_ods_is_read_and_mapped(tmp_path):
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    document = OpenDocumentSpreadsheet()
    table = Table(name="Vidas")
    for values in (
        ["Sub", "Modulos", "Nomes", "Data de Nascimento", "CPF", "Data de Admissao"],
        ["Matriz", "VGC", "Ana Silva", "12/03/1985", "52998224725", "01/02/2020"],
    ):
        row = TableRow()
        for value in values:
            cell = TableCell()
            cell.addElement(P(text=value))
            row.addElement(cell)
        table.addElement(row)
    document.spreadsheet.addElement(table)
    path = tmp_path / "vidas.ods"
    document.save(str(path))

    headers, records = parse_spreadsheet("vidas.ods", path.read_bytes())

    assert map_and_validate(headers, records, MAPPING)[0]["erros"] == []


def test_google_sheet_link_validation_accepts_only_google_sheets_https_links():
    assert importacao_api._validate_google_link(
        "https://docs.google.com/spreadsheets/d/sheet-id/edit?gid=12"
    ) == ("sheet-id", "12")

    with pytest.raises(HTTPException) as insecure:
        importacao_api._validate_google_link("http://docs.google.com/spreadsheets/d/id/edit")
    assert insecure.value.status_code == 422

    with pytest.raises(HTTPException) as external:
        importacao_api._validate_google_link("https://example.com/spreadsheets/d/id/edit")
    assert external.value.status_code == 422


class _FakeInitialImportRepository:
    def __init__(self):
        self.saved = None

    def criar(self, rows, usuario):
        self.saved = (rows, usuario)
        return {
            "id_importacao": "12345678-1234-1234-1234-123456789012",
            "cd_status": "RV",
            "total_registros": len(rows),
            "total_validos": sum(not row["erros"] for row in rows),
            "total_erros": sum(bool(row["erros"]) for row in rows),
        }

    def listar(self, limite):
        return [{"id_importacao": "12345678-1234-1234-1234-123456789012"}]

    def obter(self, importacao_id):
        return {"id_importacao": importacao_id, "itens": []}


@pytest.fixture
def api_client(monkeypatch):
    repository = _FakeInitialImportRepository()
    monkeypatch.setattr(importacao_api, "importacao_inicial_repository", repository)
    _api_app.dependency_overrides[get_current_user] = lambda: {
        "cd_role": "ADMIN",
        "cd_usuario": 1,
    }
    with TestClient(_api_app) as client:
        yield client, repository
    _api_app.dependency_overrides.pop(get_current_user, None)


def test_api_analyze_validate_save_and_read_use_same_review_lot(api_client):
    client, repository = api_client
    file = ("vidas.csv", SAMPLE_CSV, "text/csv")

    analysis = client.post(
        "/api/cadastros/importacoes-iniciais/analisar",
        files={"arquivo": file},
    )
    assert analysis.status_code == 200
    assert analysis.json()["amostra"][0][4] == "***7890"
    assert analysis.json()["amostra"][0][6:] == ["", ""]

    validate = client.post(
        "/api/cadastros/importacoes-iniciais/validar",
        files={"arquivo": file},
        data={"mapeamento": json.dumps(MAPPING)},
    )
    assert validate.status_code == 200
    assert validate.json()["total_validos"] == 2
    assert repository.saved is None

    created = client.post(
        "/api/cadastros/importacoes-iniciais",
        files={"arquivo": file},
        data={
            "mapeamento": json.dumps(MAPPING),
            "hash_conteudo": analysis.json()["hash_conteudo"],
        },
    )
    assert created.status_code == 200
    assert created.json()["cd_status"] == "RV"
    assert repository.saved[1] == "WEB00001"
    assert repository.saved[0][0]["cpf"] == "01234567890"

    assert client.get("/api/cadastros/importacoes-iniciais").status_code == 200
    assert (
        client.get(
            "/api/cadastros/importacoes-iniciais/12345678-1234-1234-1234-123456789012"
        ).status_code
        == 200
    )


def test_api_rejects_changed_content_between_validation_and_save(api_client):
    client, _ = api_client

    response = client.post(
        "/api/cadastros/importacoes-iniciais",
        files={"arquivo": ("vidas.csv", SAMPLE_CSV, "text/csv")},
        data={"mapeamento": json.dumps(MAPPING), "hash_conteudo": "outro-hash"},
    )

    assert response.status_code == 409


def test_api_analyzes_public_google_sheet_link(api_client, monkeypatch):
    client, _ = api_client

    async def download_public_sheet(_link):
        return "google-sheets.csv", SAMPLE_CSV

    monkeypatch.setattr(importacao_api, "_download_public_sheet", download_public_sheet)
    response = client.post(
        "/api/cadastros/importacoes-iniciais/analisar",
        data={
            "link_google": (
                "https://docs.google.com/spreadsheets/d/sheet-id/edit?gid=0"
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["origem"] == "Google Sheets"
    assert response.json()["mapeamento_sugerido"] == MAPPING


def test_api_returns_503_when_db2_is_unavailable(api_client, monkeypatch):
    client, repository = api_client

    def unavailable(_rows, _user):
        raise Db2Unavailable("DB2_DSN não foi configurado.")

    monkeypatch.setattr(repository, "criar", unavailable)
    analysis = client.post(
        "/api/cadastros/importacoes-iniciais/analisar",
        files={"arquivo": ("vidas.csv", SAMPLE_CSV, "text/csv")},
    ).json()
    response = client.post(
        "/api/cadastros/importacoes-iniciais",
        files={"arquivo": ("vidas.csv", SAMPLE_CSV, "text/csv")},
        data={
            "mapeamento": json.dumps(MAPPING),
            "hash_conteudo": analysis["hash_conteudo"],
        },
    )

    assert response.status_code == 503
    assert "DB2_DSN" in response.json()["detail"]
