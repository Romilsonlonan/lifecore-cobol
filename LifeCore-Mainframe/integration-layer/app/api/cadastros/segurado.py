"""
Cadastros — Segurado / Pessoa Física
GET    /api/cadastros/segurados
POST   /api/cadastros/segurados
GET    /api/cadastros/segurados/{cd_cpf}
PUT    /api/cadastros/segurados/{cd_cpf}
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.lifecore import StatusGeralEnum

router = APIRouter()


class SeguradoCreate(BaseModel):
    cd_cpf: str = Field(
        ..., min_length=11, max_length=11, description="CPF sem pontuação"
    )
    nm_segurado: str = Field(..., max_length=80)
    dt_nascimento: str = Field(..., pattern=r"^\d{8}$", description="AAAAMMDD")
    cd_sexo: str = Field(..., pattern=r"^[MFI]$", description="M/F/I")
    nm_mae: str | None = Field(None, max_length=80)
    cd_empresa: int
    nr_matricula: str | None = Field(None, max_length=20)
    vl_salario: float | None = None
    cd_cargo: str | None = Field(None, max_length=6)


class SeguradoResponse(SeguradoCreate):
    cd_segurado: int
    cd_status: StatusGeralEnum
    dt_inclusao: str
    ts_inclusao: datetime

    class Config:
        from_attributes = True


_DB: dict[str, dict] = {
    "12345678901": {
        "cd_segurado": 1,
        "cd_cpf": "12345678901",
        "nm_segurado": "JOSE DA SILVA",
        "dt_nascimento": "19800115",
        "cd_sexo": "M",
        "nm_mae": "MARIA DA SILVA",
        "cd_empresa": 1,
        "nr_matricula": "MAT001",
        "vl_salario": 5000.00,
        "cd_cargo": "ANALST",
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": "20240101",
        "ts_inclusao": datetime(2024, 1, 1, 8, 0, 0),
    }
}
_NEXT_ID = 2


def _validar_cpf(cpf: str) -> bool:
    """Validação do dígito verificador do CPF."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


@router.get("", response_model=list[SeguradoResponse], summary="Lista segurados")
def listar_segurados(cd_empresa: int | None = None):
    result = list(_DB.values())
    if cd_empresa:
        result = [s for s in result if s["cd_empresa"] == cd_empresa]
    return result


@router.post(
    "",
    response_model=SeguradoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra segurado",
)
def criar_segurado(payload: SeguradoCreate):
    global _NEXT_ID
    if not _validar_cpf(payload.cd_cpf):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CPF {payload.cd_cpf} inválido.",
        )
    if payload.cd_cpf in _DB:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CPF {payload.cd_cpf} já cadastrado.",
        )
    segurado = {
        "cd_segurado": _NEXT_ID,
        **payload.model_dump(),
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": datetime.today().strftime("%Y%m%d"),
        "ts_inclusao": datetime.utcnow(),
    }
    _DB[payload.cd_cpf] = segurado
    _NEXT_ID += 1
    return segurado


@router.get("/{cd_cpf}", response_model=SeguradoResponse, summary="Detalha segurado")
def detalhar_segurado(cd_cpf: str):
    s = _DB.get(cd_cpf)
    if not s:
        raise HTTPException(404, detail=f"Segurado CPF {cd_cpf} não encontrado.")
    return s


@router.put("/{cd_cpf}", response_model=SeguradoResponse, summary="Atualiza segurado")
def atualizar_segurado(cd_cpf: str, payload: SeguradoCreate):
    if cd_cpf not in _DB:
        raise HTTPException(404, detail=f"Segurado CPF {cd_cpf} não encontrado.")
    _DB[cd_cpf].update(payload.model_dump())
    return _DB[cd_cpf]
