"""
Pessoas — Cadastro unificado de pessoas físicas e jurídicas
(Corretores, Beneficiários, Responsáveis Técnicos, etc.)
GET    /api/pessoas
POST   /api/pessoas
GET    /api/pessoas/{cd_pessoa}
PUT    /api/pessoas/{cd_pessoa}
GET    /api/pessoas/{cd_pessoa}/apolices  (vínculos)
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.lifecore import StatusGeralEnum, TipoPessoaEnum

router = APIRouter()

_DB: dict[int, dict] = {
    1: {
        "cd_pessoa": 1,
        "tp_pessoa": TipoPessoaEnum.FISICA,
        "cd_cpf_cnpj": "98765432100",
        "nm_pessoa": "ANA CORRETOR",
        "dt_nascimento": "19850320",
        "cd_sexo": "F",
        "cd_email": "ana@corretora.com.br",  # presidio: ignore
        "nr_telefone": "11987654321",
        "cd_tipo_relacao": "COR",  # Corretor
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": "20240101",
        "ts_inclusao": datetime(2024, 1, 1, 8, 0, 0),
        "_apolices": [],
    }
}
_NEXT_ID = 2

_TIPOS_RELACAO = {
    "COR": "Corretor",
    "BEN": "Beneficiário",
    "RES": "Responsável Técnico",
    "REP": "Representante Legal",
    "DEP": "Dependente",
}


class PessoaCreate(BaseModel):
    tp_pessoa: TipoPessoaEnum
    cd_cpf_cnpj: str = Field(..., min_length=11, max_length=14)
    nm_pessoa: str = Field(..., max_length=80)
    dt_nascimento: str | None = Field(None, pattern=r"^\d{8}$")
    cd_sexo: str | None = Field(None, pattern=r"^[MFI]$")
    cd_email: str | None = Field(None, max_length=80)
    nr_telefone: str | None = Field(None, max_length=20)
    cd_tipo_relacao: str = Field(
        ..., description=f"Tipos: {list(_TIPOS_RELACAO.keys())}"
    )


class PessoaResponse(PessoaCreate):
    cd_pessoa: int
    nm_tipo_relacao: str
    cd_status: StatusGeralEnum
    dt_inclusao: str
    ts_inclusao: datetime

    class Config:
        from_attributes = True


class VinculoApoliceResponse(BaseModel):
    nr_apolice: str
    cd_produto: str
    cd_papel: str  # BEN / COR / etc.
    pct_participacao: float | None = None


@router.get("", response_model=list[PessoaResponse], summary="Lista pessoas")
def listar_pessoas(cd_tipo_relacao: str | None = None):
    result = list(_DB.values())
    if cd_tipo_relacao:
        result = [p for p in result if p.get("cd_tipo_relacao") == cd_tipo_relacao]
    return [_to_response(p) for p in result]


@router.post(
    "",
    response_model=PessoaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra pessoa",
)
def criar_pessoa(payload: PessoaCreate):
    global _NEXT_ID
    if payload.cd_tipo_relacao not in _TIPOS_RELACAO:
        raise HTTPException(
            422,
            detail=f"Tipo de relação '{payload.cd_tipo_relacao}' inválido. Válidos: {list(_TIPOS_RELACAO.keys())}",
        )
    for p in _DB.values():
        if p["cd_cpf_cnpj"] == payload.cd_cpf_cnpj:
            raise HTTPException(
                409, detail=f"CPF/CNPJ {payload.cd_cpf_cnpj} já cadastrado."
            )
    pessoa = {
        "cd_pessoa": _NEXT_ID,
        **payload.model_dump(),
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": datetime.today().strftime("%Y%m%d"),
        "ts_inclusao": datetime.utcnow(),
        "_apolices": [],
    }
    _DB[_NEXT_ID] = pessoa
    _NEXT_ID += 1
    return _to_response(pessoa)


@router.get("/{cd_pessoa}", response_model=PessoaResponse, summary="Detalha pessoa")
def detalhar_pessoa(cd_pessoa: int):
    p = _DB.get(cd_pessoa)
    if not p:
        raise HTTPException(404, detail=f"Pessoa {cd_pessoa} não encontrada.")
    return _to_response(p)


@router.put("/{cd_pessoa}", response_model=PessoaResponse, summary="Atualiza pessoa")
def atualizar_pessoa(cd_pessoa: int, payload: PessoaCreate):
    if cd_pessoa not in _DB:
        raise HTTPException(404, detail=f"Pessoa {cd_pessoa} não encontrada.")
    _DB[cd_pessoa].update(payload.model_dump())
    return _to_response(_DB[cd_pessoa])


@router.get(
    "/{cd_pessoa}/apolices",
    response_model=list[VinculoApoliceResponse],
    summary="Lista apólices vinculadas à pessoa",
)
def listar_apolices_pessoa(cd_pessoa: int):
    p = _DB.get(cd_pessoa)
    if not p:
        raise HTTPException(404, detail=f"Pessoa {cd_pessoa} não encontrada.")
    return p.get("_apolices", [])


def _to_response(p: dict) -> dict:
    return {
        **p,
        "nm_tipo_relacao": _TIPOS_RELACAO.get(
            p.get("cd_tipo_relacao", ""), "Desconhecido"
        ),
    }
