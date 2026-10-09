"""
Sinistro — Kit ECM (documentos digitais vinculados ao sinistro)
GET    /api/sinistro/{nr_sinistro}/documentos
POST   /api/sinistro/{nr_sinistro}/documentos
DELETE /api/sinistro/{nr_sinistro}/documentos/{cd_doc_ecm}

Persistência: Supabase (tabela `sinistro_docs_ecm`).
Fallback in-memory quando Supabase não configurado.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

_DB: dict[int, dict] = {}  # fallback in-memory
_NEXT_ID = 1

_GRUPOS_VALIDOS = {
    "SIN": ["Atestado Óbito", "BI", "Certidão Óbito", "Exame Médico", "Laudo INSS"],
    "APO": ["Proposta", "Certificado", "Endosso"],
    "COB": ["Contrato Social", "CNPJ", "Procuração"],
}


class DocECMCreate(BaseModel):
    nm_grupo: str = Field(..., description="Grupo: SIN / APO / COB")
    nm_tipo: str = Field(..., max_length=60)
    nr_ref: str | None = Field(None, max_length=20, description="Nº apólice ou sinistro")
    nm_arquivo: str = Field(..., max_length=100)
    ds_observacao: str | None = Field(None, max_length=200)
    id_usuario_incl: str = Field(..., max_length=20)


class DocECMResponse(DocECMCreate):
    cd_doc_ecm: int
    dt_gravacao: str
    hr_gravacao: str
    fl_selecionado: str

    class Config:
        from_attributes = True


def _sb_ok(table: str = "sinistro_docs_ecm") -> bool:
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


@router.get(
    "/{nr_sinistro}/documentos",
    response_model=list[DocECMResponse],
    summary="Lista documentos ECM do sinistro",
)
def listar_documentos(nr_sinistro: str, nm_grupo: str | None = None):
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            filters: dict = {"nr_sinistro": nr_sinistro}
            if nm_grupo:
                filters["nm_grupo"] = nm_grupo
            return sr.get_all("sinistro_docs_ecm", filters=filters, order="ts_inclusao")
    except Exception as exc:
        logger.warning("Supabase listar_documentos falhou: %s", exc)

    result = [d for d in _DB.values() if d.get("nr_ref") == nr_sinistro]
    if nm_grupo:
        result = [d for d in result if d["nm_grupo"] == nm_grupo]
    return result


@router.post(
    "/{nr_sinistro}/documentos",
    response_model=DocECMResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Anexa documento ao sinistro",
)
def anexar_documento(nr_sinistro: str, payload: DocECMCreate):
    global _NEXT_ID
    if payload.nm_grupo not in _GRUPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Grupo '{payload.nm_grupo}' inválido. Válidos: {list(_GRUPOS_VALIDOS.keys())}",
        )
    agora = datetime.now(UTC)
    row = {
        **payload.model_dump(),
        "nr_sinistro": nr_sinistro,
        "nr_ref": nr_sinistro,
        "dt_gravacao": agora.strftime("%Y%m%d"),
        "hr_gravacao": agora.strftime("%H%M%S"),
        "fl_selecionado": "S",
    }

    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            saved = sr.insert("sinistro_docs_ecm", row)
            return saved
    except Exception as exc:
        logger.warning("Supabase anexar_documento falhou: %s", exc)

    doc = {"cd_doc_ecm": _NEXT_ID, **row}
    _DB[_NEXT_ID] = doc
    _NEXT_ID += 1
    return doc


@router.delete(
    "/{nr_sinistro}/documentos/{cd_doc_ecm}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove documento ECM",
)
def remover_documento(nr_sinistro: str, cd_doc_ecm: int):
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            doc = sr.get_one("sinistro_docs_ecm", {"cd_doc_ecm": cd_doc_ecm})
            if not doc or doc.get("nr_sinistro") != nr_sinistro:
                raise HTTPException(
                    404,
                    detail=f"Documento {cd_doc_ecm} não encontrado para sinistro {nr_sinistro}.",
                )
            sr.delete("sinistro_docs_ecm", {"cd_doc_ecm": cd_doc_ecm})
            return
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Supabase remover_documento falhou: %s", exc)

    doc = _DB.get(cd_doc_ecm)
    if not doc or doc.get("nr_ref") != nr_sinistro:
        raise HTTPException(
            404,
            detail=f"Documento {cd_doc_ecm} não encontrado para sinistro {nr_sinistro}.",
        )
    del _DB[cd_doc_ecm]
