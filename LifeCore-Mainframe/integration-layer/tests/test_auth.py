"""
Testes da Auth Layer
Cobre: login, refresh, logout, me, CRUD usuários, RBAC, bloqueio.
"""

import os

os.environ["BATCH_CONNECTOR"] = "stub"
os.environ["OTEL_ENABLED"] = "false"
os.environ["RAG_CHROMA_PATH"] = "/tmp/lc_chroma_auth_test"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-32chars"
os.environ["AUTH_MAX_LOGIN_ATTEMPTS"] = "3"

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# ── Credenciais seed ──────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@lifecore.com.br"
ADMIN_SENHA = "lifecore@2026"


def _login(email=ADMIN_EMAIL, senha=ADMIN_SENHA) -> dict:
    r = client.post("/auth/login", json={"cd_email": email, "ds_senha": senha})
    assert r.status_code == 200, f"Login falhou: {r.text}"
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════


def test_login_admin_ok():
    data = _login()
    assert data["cd_role"] == "ADMIN"
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["nm_nome"] == "Administrador LifeCore"
    assert data["cd_empresa"] == 1


def test_login_senha_errada():
    r = client.post("/auth/login", json={"cd_email": ADMIN_EMAIL, "ds_senha": "errada"})
    assert r.status_code == 401
    assert (
        "tentativa" in r.json()["detail"].lower()
        or "credenciais" in r.json()["detail"].lower()
    )


def test_login_email_inexistente():
    r = client.post(
        "/auth/login", json={"cd_email": "nao@existe.com", "ds_senha": "qualquer"}
    )
    assert r.status_code == 401
    assert "inválidas" in r.json()["detail"]


def test_login_bloqueio_apos_tentativas():
    """Após AUTH_MAX_LOGIN_ATTEMPTS=3 falhas, conta é bloqueada."""
    # Cria usuário temporário para não bloquear o admin
    from app.auth.models import (
        _EMAIL_IDX,
        _USUARIOS,
        RoleEnum,
        UsuarioCreate,
        criar_usuario,
    )

    payload = UsuarioCreate(
        nm_nome="Bloqueio Test",
        cd_email="bloqueio@test.com",
        ds_senha="senha123",
        cd_role=RoleEnum.LEITURA,
        cd_empresa=1,
    )
    u = criar_usuario(payload, "test")
    uid = u["cd_usuario"]

    for i in range(3):
        r = client.post(
            "/auth/login", json={"cd_email": "bloqueio@test.com", "ds_senha": "errada"}
        )
        assert r.status_code == 401

    # 4ª tentativa — conta bloqueada
    r = client.post(
        "/auth/login", json={"cd_email": "bloqueio@test.com", "ds_senha": "errada"}
    )
    assert r.status_code in (401, 403)

    # Cleanup
    del _USUARIOS[uid]
    del _EMAIL_IDX["bloqueio@test.com"]


# ═══════════════════════════════════════════════════════════════════════════════
# ME
# ═══════════════════════════════════════════════════════════════════════════════


def test_me_com_token():
    tokens = _login()
    r = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["cd_email"] == ADMIN_EMAIL
    assert r.json()["cd_role"] == "ADMIN"


def test_me_sem_token():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_token_invalido():
    r = client.get("/auth/me", headers={"Authorization": "Bearer token.invalido.aqui"})
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# REFRESH TOKEN
# ═══════════════════════════════════════════════════════════════════════════════


def test_refresh_ok():
    tokens = _login()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    novo = r.json()
    assert "access_token" in novo
    assert "refresh_token" in novo
    # Novo refresh token deve ser diferente do anterior
    assert novo["refresh_token"] != tokens["refresh_token"]


def test_refresh_token_invalido():
    r = client.post("/auth/refresh", json={"refresh_token": "token.falso"})
    assert r.status_code == 401


def test_refresh_token_ja_usado():
    """Após rotação, o token antigo não pode ser reutilizado."""
    tokens = _login()
    # Primeiro uso — ok
    r1 = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    # Segundo uso — deve rejeitar
    r2 = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════


def test_logout_ok():
    tokens = _login()
    r = client.post(
        "/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 204
    # Depois do logout, refresh token não pode ser usado
    r2 = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD USUÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════


def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {_login()['access_token']}"}


def test_criar_usuario_operador():
    r = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "Operador Teste",
            "cd_email": "operador@lifecore.com.br",
            "ds_senha": "senha123",
            "cd_role": "OPERADOR",
            "cd_empresa": 1,
        },
        headers=_admin_headers(),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["cd_role"] == "OPERADOR"
    assert data["fl_ativo"] == "S"
    assert "ds_senha_hash" not in data  # senha nunca exposta


def test_criar_usuario_corretor():
    r = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "Corretor Silva",
            "cd_email": "corretor@corretora.com.br",
            "ds_senha": "senha456",
            "cd_role": "CORRETOR",
            "cd_empresa": 1,
            "nr_susep": "J12345",
        },
        headers=_admin_headers(),
    )
    assert r.status_code == 201
    assert r.json()["nr_susep"] == "J12345"


def test_criar_usuario_estipulante():
    r = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "RH Empresa XYZ",
            "cd_email": "rh@empresaxyz.com.br",
            "ds_senha": "senha789",
            "cd_role": "ESTIPULANTE",
            "cd_empresa": 1,
        },
        headers=_admin_headers(),
    )
    assert r.status_code == 201


def test_criar_usuario_email_duplicado():
    r = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "Duplicado",
            "cd_email": "admin@lifecore.com.br",  # já existe
            "ds_senha": "senha999",
            "cd_role": "LEITURA",
            "cd_empresa": 1,
        },
        headers=_admin_headers(),
    )
    assert r.status_code == 409


def test_criar_usuario_sem_admin():
    """Não-admin não pode criar usuários."""
    # Loga como operador (criado acima)
    tokens = _login("operador@lifecore.com.br", "senha123")
    r = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "Tentativa",
            "cd_email": "tentativa@lifecore.com.br",
            "ds_senha": "senha000",
            "cd_role": "LEITURA",
            "cd_empresa": 1,
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 403


def test_listar_usuarios():
    r = client.get("/auth/usuarios", headers=_admin_headers())
    assert r.status_code == 200
    emails = [u["cd_email"] for u in r.json()]
    assert ADMIN_EMAIL in emails


def test_detalhar_usuario_proprio():
    tokens = _login("operador@lifecore.com.br", "senha123")
    uid = tokens["cd_usuario"]
    r = client.get(
        f"/auth/usuarios/{uid}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["cd_email"] == "operador@lifecore.com.br"


def test_detalhar_usuario_outro_sem_admin():
    tokens = _login("operador@lifecore.com.br", "senha123")
    # Tenta ver o admin (id=1)
    r = client.get(
        "/auth/usuarios/1",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# ATIVAR / DESATIVAR
# ═══════════════════════════════════════════════════════════════════════════════


def test_desativar_e_ativar_usuario():
    # Cria usuário para desativar
    r_create = client.post(
        "/auth/usuarios",
        json={
            "nm_nome": "Para Desativar",
            "cd_email": "desativar@test.com",
            "ds_senha": "senha123",
            "cd_role": "LEITURA",
            "cd_empresa": 1,
        },
        headers=_admin_headers(),
    )
    uid = r_create.json()["cd_usuario"]

    # Desativa
    r_des = client.put(
        f"/auth/usuarios/{uid}/desativar",
        json={"motivo": "Funcionário desligado"},
        headers=_admin_headers(),
    )
    assert r_des.status_code == 200
    assert r_des.json()["fl_ativo"] == "N"

    # Login deve falhar
    r_login = client.post(
        "/auth/login", json={"cd_email": "desativar@test.com", "ds_senha": "senha123"}
    )
    assert r_login.status_code == 403

    # Reativa
    r_at = client.put(
        f"/auth/usuarios/{uid}/ativar",
        json={"motivo": "Recontratado"},
        headers=_admin_headers(),
    )
    assert r_at.status_code == 200
    assert r_at.json()["fl_ativo"] == "S"
    assert r_at.json()["fl_bloqueado"] == "N"

    # Login deve funcionar novamente
    r_login2 = client.post(
        "/auth/login", json={"cd_email": "desativar@test.com", "ds_senha": "senha123"}
    )
    assert r_login2.status_code == 200


def test_admin_nao_pode_desativar_a_si_mesmo():
    tokens = _login()
    r = client.put(
        "/auth/usuarios/1/desativar",
        json={},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# REDEFINIR SENHA
# ═══════════════════════════════════════════════════════════════════════════════


def test_redefinir_senha_proprio():
    tokens = _login("operador@lifecore.com.br", "senha123")
    uid = tokens["cd_usuario"]
    r = client.put(
        f"/auth/usuarios/{uid}/senha",
        json={"ds_senha_atual": "senha123", "ds_senha_nova": "novaSenha456"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200

    # Login com nova senha
    r2 = client.post(
        "/auth/login",
        json={"cd_email": "operador@lifecore.com.br", "ds_senha": "novaSenha456"},
    )
    assert r2.status_code == 200

    # Restaura senha para não quebrar outros testes
    tokens2 = r2.json()
    client.put(
        f"/auth/usuarios/{uid}/senha",
        json={"ds_senha_atual": "novaSenha456", "ds_senha_nova": "senha123"},
        headers={"Authorization": f"Bearer {tokens2['access_token']}"},
    )


def test_redefinir_senha_atual_errada():
    tokens = _login("operador@lifecore.com.br", "senha123")
    uid = tokens["cd_usuario"]
    r = client.put(
        f"/auth/usuarios/{uid}/senha",
        json={"ds_senha_atual": "ERRADA00", "ds_senha_nova": "nova12345"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# ALTERAR ROLE
# ═══════════════════════════════════════════════════════════════════════════════


def test_alterar_role():
    tokens = _login()
    uid = _login("operador@lifecore.com.br", "senha123")["cd_usuario"]
    r = client.put(
        f"/auth/usuarios/{uid}/role?cd_role=LEITURA",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["cd_role"] == "LEITURA"

    # Restaura
    client.put(
        f"/auth/usuarios/{uid}/role?cd_role=OPERADOR",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITORIA
# ═══════════════════════════════════════════════════════════════════════════════


def test_auditoria():
    r = client.get("/auth/auditoria", headers=_admin_headers())
    assert r.status_code == 200
    eventos = [e["tp_evento"] for e in r.json()]
    assert "LOGIN_OK" in eventos


def test_auditoria_sem_admin():
    tokens = _login("operador@lifecore.com.br", "senha123")
    r = client.get(
        "/auth/auditoria",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# RBAC — proteção dos outros módulos
# ═══════════════════════════════════════════════════════════════════════════════


def test_acesso_cadastros_sem_token():
    """Cadastros/empresas exige autenticação (AdminOnly aplicado)."""
    r = client.get("/api/cadastros/empresas")
    # Sem token: 401 — auth foi habilitada via AdminOnly em empresa.py
    assert r.status_code == 401


def test_jwt_invalido_retorna_401():
    r = client.get("/auth/me", headers={"Authorization": "Bearer eyJinvalido"})
    assert r.status_code == 401
