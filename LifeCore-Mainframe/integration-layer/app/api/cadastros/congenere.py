"""
Cadastros — Congênere (Ressegurador / Co-seguradora)
GET    /api/cadastros/congeneres
POST   /api/cadastros/congeneres
GET    /api/cadastros/congeneres/{cd_congenere}
DELETE /api/cadastros/congeneres/{cd_congenere}
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.schemas.lifecore import (
    CongenereCreate,
    CongenereResponse,
    StatusGeralEnum,
    TipoPessoaEnum,
)

router = APIRouter()

_DB: dict[int, dict] = {
    1: {
        "cd_congenere": 1,
        "nr_susep": "0632",
        "nm_congenere": "IRB Brasil RE",
        "tp_pessoa": TipoPessoaEnum.JURIDICA,
        "cd_empresa": 1,
        "cd_cnpj_cpf": "33098518000126",
        "cd_status": StatusGeralEnum.ATIVO,
        "ts_inclusao": datetime(2024, 1, 1, 8, 0, 0),
    }
}
_NEXT_ID = 2


@router.get("", response_model=list[CongenereResponse], summary="Lista congêneres")
def listar_congeneres(cd_empresa: int | None = None):
    result = list(_DB.values())
    if cd_empresa:
        result = [c for c in result if c.get("cd_empresa") == cd_empresa]
    return result


@router.post(
    "",
    response_model=CongenereResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra congênere",
)
def criar_congenere(payload: CongenereCreate):
    global _NEXT_ID
    for c in _DB.values():
        if c["nr_susep"] == payload.nr_susep:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SUSEP {payload.nr_susep} já cadastrado.",
            )
    congenere = {
        "cd_congenere": _NEXT_ID,
        **payload.model_dump(),
        "cd_status": StatusGeralEnum.ATIVO,
        "ts_inclusao": datetime.utcnow(),
    }
    _DB[_NEXT_ID] = congenere
    _NEXT_ID += 1
    return congenere


@router.get(
    "/{cd_congenere}", response_model=CongenereResponse, summary="Detalha congênere"
)
def detalhar_congenere(cd_congenere: int):
    c = _DB.get(cd_congenere)
    if not c:
        raise HTTPException(404, detail=f"Congênere {cd_congenere} não encontrado.")
    return c


@router.delete(
    "/{cd_congenere}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove congênere",
)
def remover_congenere(cd_congenere: int):
    if cd_congenere not in _DB:
        raise HTTPException(404, detail=f"Congênere {cd_congenere} não encontrado.")
    del _DB[cd_congenere]
