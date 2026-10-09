"""Recepção revisável de cadastros de segurados antes da configuração contratual."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.auth.dependencies import AdminOnly
from app.repositories.importacao_inicial_db2 import (
    importacao_inicial_repository,
)
from app.repositories.empresa_db2 import Db2OperationFailed, Db2Unavailable
from app.services.importacao_inicial import (
    map_and_validate,
    mask_preview_rows,
    parse_spreadsheet,
    suggested_mapping,
)

router = APIRouter()
_MAX_BYTES = 10 * 1024 * 1024
_GOOGLE_SHEET_PATH = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?$")


def _validate_google_link(link: str) -> tuple[str, str]:
    parsed = urlparse(link.strip())
    match = _GOOGLE_SHEET_PATH.fullmatch(parsed.path)
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com" or not match:
        raise HTTPException(
            status_code=422,
            detail="Use o link https://docs.google.com/spreadsheets/d/... da planilha compartilhada como leitor.",
        )
    gid = parse_qs(parsed.query).get("gid", ["0"])[0]
    if not gid.isdigit():
        raise HTTPException(status_code=422, detail="A aba selecionada no link não é válida.")
    return match.group(1), gid


async def _download_public_sheet(link: str) -> tuple[str, bytes]:
    sheet_id, gid = _validate_google_link(link)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    allowed_hosts = {"docs.google.com"}
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(4):
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        break
                    url = urljoin(url, location)
                    parsed = urlparse(url)
                    host = parsed.hostname or ""
                    if parsed.scheme != "https" or not (
                        host in allowed_hosts
                        or host == "googleusercontent.com"
                        or host.endswith(".googleusercontent.com")
                    ):
                        raise HTTPException(
                            status_code=422,
                            detail="O link da planilha redirecionou para um domínio não permitido.",
                        )
                    continue
                if response.status_code in (401, 403):
                    raise HTTPException(
                        status_code=422,
                        detail="Não foi possível ler a planilha. Compartilhe-a como 'qualquer pessoa com o link — leitor'.",
                    )
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=422,
                        detail=f"O Google Sheets não disponibilizou o arquivo (HTTP {response.status_code}).",
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > _MAX_BYTES:
                        raise HTTPException(status_code=413, detail="A planilha excede 10 MB.")
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type or b"<html" in content[:200].lower():
                    raise HTTPException(
                        status_code=422,
                        detail="O Google retornou uma página de acesso, não os dados CSV. Verifique o compartilhamento público.",
                    )
                return "google-sheets.csv", bytes(content)
    raise HTTPException(status_code=422, detail="Não foi possível baixar a planilha pública.")


async def _get_source(
    arquivo: UploadFile | None,
    link_google: str | None,
) -> tuple[str, bytes, str]:
    if bool(arquivo) == bool(link_google and link_google.strip()):
        raise HTTPException(
            status_code=422,
            detail="Envie um arquivo ou informe o link público do Google Sheets, não ambos.",
        )
    if link_google and link_google.strip():
        filename, content = await _download_public_sheet(link_google)
        return filename, content, "Google Sheets"
    assert arquivo is not None
    filename = arquivo.filename or ""
    if not filename.lower().endswith((".csv", ".xlsx", ".xls", ".ods")):
        raise HTTPException(status_code=422, detail="Use arquivo CSV, XLSX, XLS ou ODS.")
    content = await arquivo.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="A planilha excede 10 MB.")
    return filename, content, filename


async def _parse_source(
    arquivo: UploadFile | None,
    link_google: str | None,
) -> tuple[list[str], list[list[str]], str, str]:
    filename, content, source = await _get_source(arquivo, link_google)
    try:
        headers, records = parse_spreadsheet(filename, content)
    except (ValueError, UnicodeDecodeError, OSError, ImportError) as exc:
        raise HTTPException(status_code=422, detail=f"Não foi possível ler a planilha: {exc}") from exc
    return headers, records, source, sha256(content).hexdigest()


@router.post("/analisar", summary="Analisa cabeçalhos de cadastro inicial")
async def analisar_importacao_inicial(
    arquivo: UploadFile | None = File(None),
    link_google: str | None = Form(None),
    current: dict = AdminOnly,
):
    headers, records, source, content_hash = await _parse_source(arquivo, link_google)
    mapping = suggested_mapping(headers)
    preview = mask_preview_rows(headers, records)
    return {
        "origem": source,
        "hash_conteudo": content_hash,
        "cabecalhos": [
            {"indice": index, "nome": header}
            for index, header in enumerate(headers)
        ],
        "mapeamento_sugerido": mapping,
        "amostra": preview,
        "total_linhas": len(records),
        "campos_obrigatorios": [
            "subestipulante",
            "modulo",
            "nome_segurado",
            "dt_nascimento",
            "cpf",
            "dt_admissao",
        ],
        "campos_ignorados": ["salario", "cargo", "capital"],
    }


@router.post("/validar", summary="Valida o mapeamento sem gravar no DB2")
async def validar_importacao_inicial(
    arquivo: UploadFile | None = File(None),
    link_google: str | None = Form(None),
    mapeamento: str = Form(...),
    current: dict = AdminOnly,
):
    headers, records, source, content_hash = await _parse_source(arquivo, link_google)
    try:
        column_mapping = json.loads(mapeamento)
        if not isinstance(column_mapping, dict):
            raise ValueError("O mapeamento deve ser um objeto JSON.")
        rows = map_and_validate(headers, records, column_mapping)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "origem": source,
        "hash_conteudo": content_hash,
        "total_linhas": len(rows),
        "total_validos": sum(not row["erros"] for row in rows),
        "total_erros": sum(bool(row["erros"]) for row in rows),
        "amostra": [
            {
                **row,
                "cpf": f"***{row['cpf'][-4:]}" if row["cpf"] else "",
            }
            for row in rows[:10]
        ],
    }


@router.post("", summary="Salva lote de cadastro inicial para revisão")
async def criar_importacao_inicial(
    arquivo: UploadFile | None = File(None),
    link_google: str | None = Form(None),
    mapeamento: str = Form(...),
    hash_conteudo: str = Form(...),
    current: dict = AdminOnly,
):
    headers, records, _, content_hash = await _parse_source(arquivo, link_google)
    if content_hash != hash_conteudo:
        raise HTTPException(
            status_code=409,
            detail="A planilha mudou desde a validação. Analise e valide novamente antes de salvar.",
        )
    try:
        column_mapping = json.loads(mapeamento)
        if not isinstance(column_mapping, dict):
            raise ValueError("O mapeamento deve ser um objeto JSON.")
        rows = map_and_validate(headers, records, column_mapping)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = importacao_inicial_repository.criar(
            rows, f"WEB{current['cd_usuario']:05d}"
        )
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result


@router.get("", summary="Lista lotes de cadastro inicial no DB2")
def listar_importacoes_iniciais(
    limite: int = Query(20, ge=1, le=100),
    current: dict = AdminOnly,
):
    try:
        return importacao_inicial_repository.listar(limite)
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{id_importacao}", summary="Consulta lote de cadastro inicial no DB2")
def obter_importacao_inicial(
    id_importacao: str,
    current: dict = AdminOnly,
):
    if not re.fullmatch(r"[A-Fa-f0-9-]{36}", id_importacao):
        raise HTTPException(status_code=422, detail="Identificador de importação inválido.")
    try:
        result = importacao_inicial_repository.obter(id_importacao)
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Lote de importação não encontrado.")
    return result
