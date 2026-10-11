"""
Cadastros — Empresa / Estipulante / Seguradora
GET    /api/cadastros/empresas
POST   /api/cadastros/empresas
GET    /api/cadastros/empresas/{cd_empresa}
PUT    /api/cadastros/empresas/{cd_empresa}/status
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import AdminOnly
from app.repositories.empresa_db2 import (
    Db2OperationFailed,
    Db2Unavailable,
    EmpresaAlreadyExists,
    EmpresaNotFound,
    empresa_repository,
)
from app.schemas.lifecore import (
    EmpresaCreate,
    EmpresaResponse,
    StatusGeralEnum,
)

router = APIRouter()


@router.get("", response_model=list[EmpresaResponse], summary="Lista empresas")
def listar_empresas(
    status: StatusGeralEnum | None = None,
    current: dict = AdminOnly,
):
    """Retorna empresas lidas diretamente da tabela DB2 compartilhada com CICS."""
    try:
        return empresa_repository.listar(status)
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "",
    response_model=EmpresaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra empresa",
)
def criar_empresa(
    payload: EmpresaCreate,
    current: dict = AdminOnly,
):
    """Cadastra uma nova empresa no DB2 compartilhado com o CICS."""
    try:
        return empresa_repository.criar(payload, f"WEB{current['cd_usuario']:05d}")
    except EmpresaAlreadyExists as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{cd_empresa}", response_model=EmpresaResponse, summary="Detalha empresa")
def detalhar_empresa(
    cd_empresa: int,
    current: dict = AdminOnly,
):
    try:
        return empresa_repository.obter(cd_empresa)
    except EmpresaNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {cd_empresa} não encontrada.",
        ) from exc
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put(
    "/{cd_empresa}/status",
    response_model=EmpresaResponse,
    summary="Ativa / Inativa empresa",
)
def alterar_status_empresa(
    cd_empresa: int,
    cd_status: StatusGeralEnum,
    current: dict = AdminOnly,
):
    try:
        return empresa_repository.alterar_status(cd_empresa, cd_status)
    except EmpresaNotFound as exc:
        raise HTTPException(
            status_code=404, detail=f"Empresa {cd_empresa} não encontrada."
        ) from exc
    except (Db2Unavailable, Db2OperationFailed) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
