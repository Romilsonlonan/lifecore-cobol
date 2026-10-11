"""
Auth Layer — Dependências FastAPI
Injeção de usuário autenticado + verificação de roles (RBAC)
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.auth.models import (
    RoleEnum,
    UsuarioResponse,
    buscar_por_id,
    decodificar_token,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _extrair_usuario(token: str) -> dict:
    """Decodifica JWT e retorna o dict do usuário. Levanta 401 se inválido."""
    try:
        payload = decodificar_token(token)
        if payload.get("type") != "access":
            raise ValueError("tipo de token inválido")
        cd_usuario = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = buscar_por_id(cd_usuario)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    if usuario["fl_ativo"] != "S":
        raise HTTPException(status_code=403, detail="Usuário inativo.")
    if usuario["fl_bloqueado"] == "S":
        raise HTTPException(
            status_code=403, detail="Usuário bloqueado por excesso de tentativas."
        )

    return usuario


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Retorna o dict do usuário autenticado."""
    return _extrair_usuario(token)


def get_current_user_response(token: str = Depends(oauth2_scheme)) -> UsuarioResponse:
    """Retorna UsuarioResponse do usuário autenticado."""
    u = _extrair_usuario(token)
    return UsuarioResponse(**{k: v for k, v in u.items() if k != "ds_senha_hash"})


# ── Verificadores de role ─────────────────────────────────────────────────────


def require_role(*roles: RoleEnum):
    """
    Factory de dependência que exige um dos roles especificados.

    Uso:
        @router.post("/...", dependencies=[Depends(require_role(RoleEnum.ADMIN))])
    """

    def _check(current: dict = Depends(get_current_user)) -> dict:
        role = current.get("cd_role")
        # Aceita tanto enum quanto string
        role_str = role.value if isinstance(role, RoleEnum) else role
        allowed = {r.value for r in roles}
        if role_str not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Role necessário: {[r.value for r in roles]}.",
            )
        return current

    return _check


def require_same_empresa(
    cd_empresa: int, current: dict = Depends(get_current_user)
) -> dict:
    """
    Garante que o usuário só acessa dados da própria empresa,
    a menos que seja ADMIN.
    """
    role = current.get("cd_role")
    role_str = role.value if isinstance(role, RoleEnum) else role
    if role_str != RoleEnum.ADMIN.value and current["cd_empresa"] != cd_empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado — empresa diferente da sua.",
        )
    return current


# Dependências prontas para usar nos routers
AdminOnly = Depends(require_role(RoleEnum.ADMIN))
EscritaOuAdmin = Depends(require_role(RoleEnum.ADMIN, RoleEnum.OPERADOR))
QualquerAutenticado = Depends(get_current_user)
