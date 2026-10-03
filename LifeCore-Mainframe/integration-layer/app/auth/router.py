"""
Auth Layer — Router
POST /auth/login                    → autenticação → JWT
POST /auth/refresh                  → renova access token
POST /auth/logout                   → revoga refresh token
GET  /auth/me                       → perfil do usuário logado

POST /auth/usuarios                 → cria usuário (ADMIN)
GET  /auth/usuarios                 → lista usuários (ADMIN)
GET  /auth/usuarios/{id}            → detalha (ADMIN ou próprio)
PUT  /auth/usuarios/{id}/ativar     → ativa acesso (ADMIN)
PUT  /auth/usuarios/{id}/desativar  → bloqueia acesso (ADMIN)
PUT  /auth/usuarios/{id}/senha      → redefine senha (próprio ou ADMIN)
PUT  /auth/usuarios/{id}/role       → altera role (ADMIN)
DELETE /auth/usuarios/{id}          → remove (ADMIN)
"""
from __future__ import annotations

import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.auth.models import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UsuarioCreate,
    UsuarioResponse,
    RedefinirSenhaRequest,
    AlterarStatusRequest,
    RoleEnum,
    ACCESS_EXPIRE_MIN,
    REFRESH_EXPIRE_H,
    MAX_LOGIN_ATTEMPTS,
    _TOKENS_REVOGADOS,
    buscar_por_email,
    buscar_por_id,
    criar_usuario,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
    hash_senha,
    verificar_senha,
    registrar_login_ok,
    registrar_falha_login,
    listar_usuarios,
)
from app.auth.dependencies import (
    get_current_user,
    get_current_user_response,
    require_role,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Store de refresh tokens: hash → {cd_usuario, expira, revogado}
_REFRESH_STORE: dict[str, dict] = {}

# Auditoria em memória (em produção: gravar em SESSAO_AUDITORIA)
_AUDIT: list[dict] = []


def _auditar(tp_evento: str, cd_usuario: Optional[int], ip: str, detalhe: str = ""):
    _AUDIT.append({
        "tp_evento":   tp_evento,
        "cd_usuario":  cd_usuario,
        "ip_origem":   ip,
        "ds_detalhe":  detalhe,
        "ts_evento":   datetime.now(timezone.utc).isoformat(),
    })
    logger.info("AUDIT %s uid=%s ip=%s %s", tp_evento, cd_usuario, ip, detalhe)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _to_response(u: dict) -> UsuarioResponse:
    return UsuarioResponse(**{k: v for k, v in u.items() if k != "ds_senha_hash"})


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticação — retorna JWT access + refresh token",
)
def login(payload: LoginRequest, request: Request):
    """
    Autentica usuário com e-mail e senha.
    Retorna access token (30 min) e refresh token (7 dias).
    Bloqueia após 5 tentativas inválidas consecutivas.
    """
    ip = _ip(request)
    usuario = buscar_por_email(payload.cd_email)

    if not usuario:
        _auditar("LOGIN_FAIL", None, ip, f"email={payload.cd_email} não encontrado")
        # Mesmo tempo de resposta para não revelar se o e-mail existe
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    cd = usuario["cd_usuario"]

    if usuario["fl_bloqueado"] == "S":
        _auditar("LOGIN_FAIL", cd, ip, "conta bloqueada")
        raise HTTPException(
            status_code=403,
            detail=f"Conta bloqueada após {MAX_LOGIN_ATTEMPTS} tentativas. Contate o administrador.",
        )

    if usuario["fl_ativo"] != "S":
        _auditar("LOGIN_FAIL", cd, ip, "conta inativa")
        raise HTTPException(status_code=403, detail="Conta inativa. Contate o administrador.")

    if not verificar_senha(payload.ds_senha, usuario["ds_senha_hash"]):
        tentativas = registrar_falha_login(cd)
        restantes  = max(0, MAX_LOGIN_ATTEMPTS - tentativas)
        _auditar("LOGIN_FAIL", cd, ip, f"senha incorreta — tentativa {tentativas}")
        msg = f"Credenciais inválidas. {restantes} tentativa(s) restante(s)."
        if restantes == 0:
            msg = "Conta bloqueada por excesso de tentativas. Contate o administrador."
        raise HTTPException(status_code=401, detail=msg)

    # ── Sucesso ───────────────────────────────────────────────────────────────
    registrar_login_ok(cd)
    access_token = criar_access_token(usuario)
    raw, token_hash = criar_refresh_token(cd)

    _REFRESH_STORE[token_hash] = {
        "cd_usuario": cd,
        "expira":     datetime.now(timezone.utc) + timedelta(hours=REFRESH_EXPIRE_H),
        "revogado":   False,
        "ip":         ip,
    }

    _auditar("LOGIN_OK", cd, ip)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw,
        cd_usuario=cd,
        nm_nome=usuario["nm_nome"],
        cd_role=usuario["cd_role"],
        cd_empresa=usuario["cd_empresa"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REFRESH TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renova o access token usando o refresh token",
)
def refresh_token(payload: RefreshRequest, request: Request):
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    entry      = _REFRESH_STORE.get(token_hash)

    if not entry:
        raise HTTPException(status_code=401, detail="Refresh token inválido.")
    if entry["revogado"]:
        _auditar("TOKEN_REFRESH", entry["cd_usuario"], _ip(request), "token já revogado")
        raise HTTPException(status_code=401, detail="Refresh token já utilizado ou revogado.")
    if datetime.now(timezone.utc) > entry["expira"]:
        raise HTTPException(status_code=401, detail="Refresh token expirado. Faça login novamente.")

    usuario = buscar_por_id(entry["cd_usuario"])
    if not usuario or usuario["fl_ativo"] != "S":
        raise HTTPException(status_code=401, detail="Usuário inativo.")

    # Rotação de token: revoga o atual e emite novo
    entry["revogado"] = True
    novo_access = criar_access_token(usuario)
    novo_raw, novo_hash = criar_refresh_token(entry["cd_usuario"])
    _REFRESH_STORE[novo_hash] = {
        "cd_usuario": entry["cd_usuario"],
        "expira":     datetime.now(timezone.utc) + timedelta(hours=REFRESH_EXPIRE_H),
        "revogado":   False,
        "ip":         _ip(request),
    }

    _auditar("TOKEN_REFRESH", entry["cd_usuario"], _ip(request))

    return TokenResponse(
        access_token=novo_access,
        refresh_token=novo_raw,
        cd_usuario=usuario["cd_usuario"],
        nm_nome=usuario["nm_nome"],
        cd_role=usuario["cd_role"],
        cd_empresa=usuario["cd_empresa"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Encerra sessão")
def logout(
    payload: RefreshRequest,
    request: Request,
    current: dict = Depends(get_current_user),
):
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    entry      = _REFRESH_STORE.get(token_hash)
    if entry:
        entry["revogado"] = True
    _auditar("LOGOUT", current["cd_usuario"], _ip(request))


# ═══════════════════════════════════════════════════════════════════════════════
# ME
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/me", response_model=UsuarioResponse, summary="Perfil do usuário logado")
def me(current: dict = Depends(get_current_user)):
    return _to_response(current)


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD DE USUÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria usuário (ADMIN)",
)
def criar_usuario_endpoint(
    payload: UsuarioCreate,
    request: Request,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    """
    Cria um novo usuário vinculado a uma empresa.
    Apenas ADMIN pode criar usuários.
    Roles disponíveis: ADMIN, OPERADOR, CORRETOR, ESTIPULANTE, LEITURA.
    """
    try:
        usuario = criar_usuario(payload, criado_por=current["cd_email"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _auditar(
        "USUARIO_CRIADO", current["cd_usuario"], _ip(request),
        f"novo={payload.cd_email} role={payload.cd_role} empresa={payload.cd_empresa}",
    )
    return _to_response(usuario)


@router.get(
    "/usuarios",
    response_model=list[UsuarioResponse],
    summary="Lista usuários (ADMIN)",
)
def listar_usuarios_endpoint(
    cd_empresa: Optional[int] = None,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    """Lista todos os usuários. ADMIN pode filtrar por empresa."""
    return [_to_response(u) for u in listar_usuarios(cd_empresa)]


@router.get(
    "/usuarios/{cd_usuario}",
    response_model=UsuarioResponse,
    summary="Detalha usuário",
)
def detalhar_usuario(
    cd_usuario: int,
    current: dict = Depends(get_current_user),
):
    """ADMIN vê qualquer usuário. Demais roles só veem a si mesmos."""
    role = current.get("cd_role")
    role_str = role.value if isinstance(role, RoleEnum) else role
    if role_str != RoleEnum.ADMIN.value and current["cd_usuario"] != cd_usuario:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")
    return _to_response(u)


@router.put(
    "/usuarios/{cd_usuario}/ativar",
    response_model=UsuarioResponse,
    summary="Ativa acesso do usuário (ADMIN)",
)
def ativar_usuario(
    cd_usuario: int,
    payload: AlterarStatusRequest,
    request: Request,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")
    u["fl_ativo"]             = "S"
    u["fl_bloqueado"]         = "N"
    u["nr_tentativas_falha"]  = 0
    _auditar(
        "USUARIO_ATIVADO", current["cd_usuario"], _ip(request),
        f"uid={cd_usuario} motivo={payload.motivo}",
    )
    return _to_response(u)


@router.put(
    "/usuarios/{cd_usuario}/desativar",
    response_model=UsuarioResponse,
    summary="Desativa acesso do usuário (ADMIN)",
)
def desativar_usuario(
    cd_usuario: int,
    payload: AlterarStatusRequest,
    request: Request,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")
    if cd_usuario == current["cd_usuario"]:
        raise HTTPException(status_code=400, detail="Você não pode desativar a si mesmo.")
    u["fl_ativo"] = "N"
    _auditar(
        "USUARIO_DESATIVADO", current["cd_usuario"], _ip(request),
        f"uid={cd_usuario} motivo={payload.motivo}",
    )
    return _to_response(u)


@router.put(
    "/usuarios/{cd_usuario}/senha",
    response_model=UsuarioResponse,
    summary="Redefine senha (próprio usuário ou ADMIN)",
)
def redefinir_senha(
    cd_usuario: int,
    payload: RedefinirSenhaRequest,
    request: Request,
    current: dict = Depends(get_current_user),
):
    role = current.get("cd_role")
    role_str = role.value if isinstance(role, RoleEnum) else role
    is_admin = role_str == RoleEnum.ADMIN.value
    is_proprio = current["cd_usuario"] == cd_usuario

    if not is_admin and not is_proprio:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")

    # Próprio usuário deve confirmar senha atual
    if is_proprio and not is_admin:
        if not verificar_senha(payload.ds_senha_atual, u["ds_senha_hash"]):
            raise HTTPException(status_code=401, detail="Senha atual incorreta.")

    u["ds_senha_hash"] = hash_senha(payload.ds_senha_nova)
    _auditar("SENHA_RESET", current["cd_usuario"], _ip(request), f"uid={cd_usuario}")
    return _to_response(u)


@router.put(
    "/usuarios/{cd_usuario}/role",
    response_model=UsuarioResponse,
    summary="Altera role do usuário (ADMIN)",
)
def alterar_role(
    cd_usuario: int,
    cd_role: RoleEnum,
    request: Request,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")
    role_anterior = u["cd_role"]
    u["cd_role"] = cd_role
    _auditar(
        "USUARIO_ATIVADO", current["cd_usuario"], _ip(request),
        f"uid={cd_usuario} role {role_anterior} → {cd_role}",
    )
    return _to_response(u)


@router.delete(
    "/usuarios/{cd_usuario}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove usuário (ADMIN)",
)
def remover_usuario(
    cd_usuario: int,
    request: Request,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    from app.auth.models import _USUARIOS, _EMAIL_IDX
    u = buscar_por_id(cd_usuario)
    if not u:
        raise HTTPException(status_code=404, detail=f"Usuário {cd_usuario} não encontrado.")
    if cd_usuario == current["cd_usuario"]:
        raise HTTPException(status_code=400, detail="Você não pode remover a si mesmo.")
    email = u["cd_email"]
    del _USUARIOS[cd_usuario]
    _EMAIL_IDX.pop(email, None)
    _auditar("USUARIO_DESATIVADO", current["cd_usuario"], _ip(request), f"uid={cd_usuario} removido")


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITORIA DE SESSÕES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/auditoria",
    summary="Histórico de eventos de autenticação (ADMIN)",
)
def listar_auditoria(
    limit: int = 50,
    current: dict = Depends(require_role(RoleEnum.ADMIN)),
):
    return _AUDIT[-limit:]
