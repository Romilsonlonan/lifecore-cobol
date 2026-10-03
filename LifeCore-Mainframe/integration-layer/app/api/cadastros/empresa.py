"""
Cadastros — Empresa / Estipulante / Seguradora
GET    /api/cadastros/empresas
POST   /api/cadastros/empresas
GET    /api/cadastros/empresas/{cd_empresa}
PUT    /api/cadastros/empresas/{cd_empresa}/status
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.schemas.lifecore import (
    EmpresaCreate,
    EmpresaResponse,
    StatusGeralEnum,
    TipoEmpresaEnum,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Repositório em memória (stub) — substituir por SQLAlchemy em produção
# ---------------------------------------------------------------------------
_DB: dict[int, dict] = {
    1: {
        "cd_empresa": 1,
        "nr_codigo": "000001",
        "nm_razao_social": "Prudential do Brasil Seguros de Vida S.A.",
        "nm_nome_reduzido": "PRUDENTIAL BR",
        "cd_cnpj": "51990695000137",
        "tp_empresa": TipoEmpresaEnum.SEGURADORA,
        "nr_susep": "1000",
        "vl_capital_vinculado": 100_000_000.00,
        "vl_capital_subscrito": 200_000_000.00,
        "vl_aceite_cobranca": 50_000.00,
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": "20240101",
        "ts_inclusao": datetime(2024, 1, 1, 8, 0, 0),
    }
}
_NEXT_ID = 2


@router.get("", response_model=list[EmpresaResponse], summary="Lista empresas")
def listar_empresas(status: StatusGeralEnum | None = None):
    """Retorna todas as empresas cadastradas, com filtro opcional por status."""
    result = list(_DB.values())
    if status:
        result = [e for e in result if e["cd_status"] == status]
    return result


@router.post(
    "",
    response_model=EmpresaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra empresa",
)
def criar_empresa(payload: EmpresaCreate):
    """Cadastra uma nova empresa (seguradora, estipulante, corretora, etc.)."""
    global _NEXT_ID
    # CNPJ duplicado
    for e in _DB.values():
        if e["cd_cnpj"] == payload.cd_cnpj:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"CNPJ {payload.cd_cnpj} já cadastrado (cd_empresa={e['cd_empresa']}).",
            )
    empresa = {
        "cd_empresa": _NEXT_ID,
        **payload.model_dump(),
        "cd_status": StatusGeralEnum.ATIVO,
        "dt_inclusao": datetime.today().strftime("%Y%m%d"),
        "ts_inclusao": datetime.utcnow(),
    }
    _DB[_NEXT_ID] = empresa
    _NEXT_ID += 1
    return empresa


@router.get("/{cd_empresa}", response_model=EmpresaResponse, summary="Detalha empresa")
def detalhar_empresa(cd_empresa: int):
    empresa = _DB.get(cd_empresa)
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {cd_empresa} não encontrada.",
        )
    return empresa


@router.put(
    "/{cd_empresa}/status",
    response_model=EmpresaResponse,
    summary="Ativa / Inativa empresa",
)
def alterar_status_empresa(cd_empresa: int, cd_status: StatusGeralEnum):
    empresa = _DB.get(cd_empresa)
    if not empresa:
        raise HTTPException(status_code=404, detail=f"Empresa {cd_empresa} não encontrada.")
    empresa["cd_status"] = cd_status
    return empresa
