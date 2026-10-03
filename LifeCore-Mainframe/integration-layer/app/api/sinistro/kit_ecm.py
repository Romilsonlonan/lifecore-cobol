"""
Sinistro — Kit ECM (documentos digitais vinculados ao sinistro)
GET    /api/sinistro/{nr_sinistro}/documentos
POST   /api/sinistro/{nr_sinistro}/documentos
DELETE /api/sinistro/{nr_sinistro}/documentos/{cd_doc_ecm}
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()

_DB: dict[int, dict] = {}
_NEXT_ID = 1

# Grupos de documento válidos (seed da tabela GRUPO_DOC_ECM)
_GRUPOS_VALIDOS = {
    "SIN": ["Atestado Óbito", "BI", "Certidão Óbito", "Exame Médico", "Laudo INSS"],
    "APO": ["Proposta", "Certificado", "Endosso"],
    "COB": ["Contrato Social", "CNPJ", "Procuração"],
}


class DocECMCreate(BaseModel):
    nm_grupo:       str = Field(..., description="Grupo: SIN / APO / COB")
    nm_tipo:        str = Field(..., max_length=60)
    nr_ref:         Optional[str] = Field(None, max_length=20, description="Nº apólice ou sinistro")
    nm_arquivo:     str = Field(..., max_length=100, description="Nome do arquivo no storage")
    ds_observacao:  Optional[str] = Field(None, max_length=200)
    id_usuario_incl: str = Field(..., max_length=20)


class DocECMResponse(DocECMCreate):
    cd_doc_ecm:     int
    dt_gravacao:    str
    hr_gravacao:    str
    fl_selecionado: str

    class Config:
        from_attributes = True


@router.get(
    "/{nr_sinistro}/documentos",
    response_model=list[DocECMResponse],
    summary="Lista documentos ECM do sinistro",
)
def listar_documentos(nr_sinistro: str, nm_grupo: str | None = None):
    result = [
        d for d in _DB.values() if d.get("nr_ref") == nr_sinistro
    ]
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
    agora = datetime.utcnow()
    doc = {
        "cd_doc_ecm":       _NEXT_ID,
        **payload.model_dump(),
        "nr_ref":           nr_sinistro,
        "dt_gravacao":      agora.strftime("%Y%m%d"),
        "hr_gravacao":      agora.strftime("%H%M%S"),
        "fl_selecionado":   "S",
    }
    _DB[_NEXT_ID] = doc
    _NEXT_ID += 1
    return doc


@router.delete(
    "/{nr_sinistro}/documentos/{cd_doc_ecm}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove documento ECM",
)
def remover_documento(nr_sinistro: str, cd_doc_ecm: int):
    doc = _DB.get(cd_doc_ecm)
    if not doc or doc.get("nr_ref") != nr_sinistro:
        raise HTTPException(404, detail=f"Documento {cd_doc_ecm} não encontrado para sinistro {nr_sinistro}.")
    del _DB[cd_doc_ecm]
