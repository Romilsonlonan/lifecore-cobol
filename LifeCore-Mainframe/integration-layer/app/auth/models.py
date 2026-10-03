"""
Auth Layer — Modelos, hashing, JWT e store em memória
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY        = os.getenv("AUTH_SECRET_KEY", secrets.token_hex(32))
ALGORITHM         = "HS256"
ACCESS_EXPIRE_MIN = int(os.getenv("AUTH_ACCESS_EXPIRE_MIN",  "30"))
REFRESH_EXPIRE_H  = int(os.getenv("AUTH_REFRESH_EXPIRE_H",  "168"))   # 7 dias
MAX_LOGIN_ATTEMPTS = int(os.getenv("AUTH_MAX_LOGIN_ATTEMPTS", "5"))


# ── Enums ─────────────────────────────────────────────────────────────────────

class RoleEnum(str, Enum):
    ADMIN       = "ADMIN"
    OPERADOR    = "OPERADOR"
    CORRETOR    = "CORRETOR"
    ESTIPULANTE = "ESTIPULANTE"
    LEITURA     = "LEITURA"

    def pode_escrever(self) -> bool:
        return self in (RoleEnum.ADMIN, RoleEnum.OPERADOR)

    def pode_admin(self) -> bool:
        return self == RoleEnum.ADMIN


# ── Schemas ───────────────────────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    nm_nome:    str         = Field(..., min_length=3, max_length=80)
    cd_email:   str         = Field(..., description="E-mail único por empresa")
    ds_senha:   str         = Field(..., min_length=8, description="Mín 8 chars")
    cd_role:    RoleEnum    = RoleEnum.LEITURA
    cd_empresa: int         = Field(..., description="Empresa à qual o usuário pertence")
    nr_cpf:     Optional[str] = Field(None, min_length=11, max_length=11)
    nr_susep:   Optional[str] = Field(None, max_length=10, description="Para corretores")


class UsuarioResponse(BaseModel):
    cd_usuario:     int
    nm_nome:        str
    cd_email:       str
    cd_role:        RoleEnum
    cd_empresa:     int
    nm_empresa:     Optional[str] = None
    fl_ativo:       str
    fl_bloqueado:   str
    dt_inclusao:    str
    dt_ultimo_login: Optional[str] = None
    nr_susep:       Optional[str] = None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    cd_email:   str = Field(..., description="E-mail cadastrado")
    ds_senha:   str = Field(..., description="Senha")


class TokenResponse(BaseModel):
    access_token:   str
    refresh_token:  str
    token_type:     str = "bearer"
    expires_in:     int = ACCESS_EXPIRE_MIN * 60   # segundos
    cd_usuario:     int
    nm_nome:        str
    cd_role:        RoleEnum
    cd_empresa:     int


class RefreshRequest(BaseModel):
    refresh_token: str


class RedefinirSenhaRequest(BaseModel):
    ds_senha_atual: str
    ds_senha_nova:  str = Field(..., min_length=8)


class AlterarStatusRequest(BaseModel):
    motivo: Optional[str] = Field(None, max_length=200)


# ── Store em memória ──────────────────────────────────────────────────────────
# Em produção: substituir por SQLAlchemy + PostgreSQL

_USUARIOS: dict[int, dict] = {}
_TOKENS_REVOGADOS: set[str] = set()   # hashes de refresh tokens revogados
_NEXT_ID = 1

# Seed — admin padrão (senha: lifecore@2026)
_ADMIN_HASH = bcrypt.hashpw(b"lifecore@2026", bcrypt.gensalt()).decode()
_USUARIOS[1] = {
    "cd_usuario":       1,
    "cd_empresa":       1,
    "nm_nome":          "Administrador LifeCore",
    "cd_email":         "admin@lifecore.com.br",
    "ds_senha_hash":    _ADMIN_HASH,
    "cd_role":          RoleEnum.ADMIN,
    "fl_ativo":         "S",
    "fl_bloqueado":     "N",
    "nr_tentativas_falha": 0,
    "nr_cpf":           None,
    "nr_susep":         None,
    "dt_inclusao":      datetime.now().strftime("%Y%m%d"),
    "dt_ultimo_login":  None,
    "hr_ultimo_login":  None,
    "id_usuario_incl":  "SYSTEM",
}
_NEXT_ID = 2

# Índice e-mail → id
_EMAIL_IDX: dict[str, int] = {"admin@lifecore.com.br": 1}


# ── Funções de hash ───────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except Exception:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── JWT ───────────────────────────────────────────────────────────────────────

def criar_access_token(usuario: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MIN)
    payload = {
        "sub":          str(usuario["cd_usuario"]),
        "email":        usuario["cd_email"],
        "role":         usuario["cd_role"].value if isinstance(usuario["cd_role"], RoleEnum) else usuario["cd_role"],
        "empresa":      usuario["cd_empresa"],
        "nome":         usuario["nm_nome"],
        "exp":          expire,
        "type":         "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def criar_refresh_token(cd_usuario: int) -> tuple[str, str]:
    """Retorna (token_raw, token_hash). Armazena apenas o hash."""
    token_raw  = secrets.token_urlsafe(64)
    token_hash = _hash_token(token_raw)
    return token_raw, token_hash


def decodificar_token(token: str) -> dict:
    """Levanta JWTError se inválido ou expirado."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── CRUD em memória ───────────────────────────────────────────────────────────

def buscar_por_email(email: str) -> Optional[dict]:
    uid = _EMAIL_IDX.get(email.lower())
    return _USUARIOS.get(uid) if uid else None


def buscar_por_id(cd_usuario: int) -> Optional[dict]:
    return _USUARIOS.get(cd_usuario)


def criar_usuario(payload: UsuarioCreate, criado_por: str) -> dict:
    global _NEXT_ID
    email = payload.cd_email.lower()
    if email in _EMAIL_IDX:
        raise ValueError(f"E-mail {email} já cadastrado.")
    usuario = {
        "cd_usuario":       _NEXT_ID,
        "cd_empresa":       payload.cd_empresa,
        "nm_nome":          payload.nm_nome,
        "cd_email":         email,
        "ds_senha_hash":    hash_senha(payload.ds_senha),
        "cd_role":          payload.cd_role,
        "fl_ativo":         "S",
        "fl_bloqueado":     "N",
        "nr_tentativas_falha": 0,
        "nr_cpf":           payload.nr_cpf,
        "nr_susep":         payload.nr_susep,
        "dt_inclusao":      datetime.now().strftime("%Y%m%d"),
        "dt_ultimo_login":  None,
        "hr_ultimo_login":  None,
        "id_usuario_incl":  criado_por,
    }
    _USUARIOS[_NEXT_ID] = usuario
    _EMAIL_IDX[email]   = _NEXT_ID
    _NEXT_ID += 1
    return usuario


def registrar_login_ok(cd_usuario: int) -> None:
    u = _USUARIOS.get(cd_usuario)
    if u:
        agora = datetime.now()
        u["dt_ultimo_login"]      = agora.strftime("%Y%m%d")
        u["hr_ultimo_login"]      = agora.strftime("%H%M%S")
        u["nr_tentativas_falha"]  = 0


def registrar_falha_login(cd_usuario: int) -> int:
    """Incrementa tentativas. Retorna o total. Bloqueia após MAX."""
    u = _USUARIOS.get(cd_usuario)
    if not u:
        return 0
    u["nr_tentativas_falha"] += 1
    if u["nr_tentativas_falha"] >= MAX_LOGIN_ATTEMPTS:
        u["fl_bloqueado"] = "S"
    return u["nr_tentativas_falha"]


def listar_usuarios(cd_empresa: Optional[int] = None) -> list[dict]:
    result = list(_USUARIOS.values())
    if cd_empresa:
        result = [u for u in result if u["cd_empresa"] == cd_empresa]
    return result
