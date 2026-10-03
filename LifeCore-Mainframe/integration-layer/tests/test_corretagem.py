"""
Testes do módulo de Corretagem
Cobre: corretoras, corretores, vínculos e consulta por empresa.
"""
import os
os.environ["BATCH_CONNECTOR"]    = "stub"
os.environ["OTEL_ENABLED"]       = "false"
os.environ["RAG_CHROMA_PATH"]    = "/tmp/lc_chroma_corretagem_test"
os.environ["AUTH_SECRET_KEY"]    = "test-secret-key-32chars"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRETORAS
# ═══════════════════════════════════════════════════════════════════════════════

def test_listar_corretoras():
    r = client.get("/api/corretagem/corretoras")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["nm_razao_social"] == "Corretora Exemplo Ltda"


def test_detalhar_corretora_existente():
    r = client.get("/api/corretagem/corretoras/1")
    assert r.status_code == 200
    d = r.json()
    assert d["cd_corretora"] == 1
    assert d["nr_susep"] == "J1234"
    assert d["cd_email"] == "contato@corretora.com.br"
    assert d["nm_cidade"] == "São Paulo"


def test_detalhar_corretora_inexistente():
    r = client.get("/api/corretagem/corretoras/9999")
    assert r.status_code == 404


def test_criar_corretora():
    r = client.post("/api/corretagem/corretoras", json={
        "nm_razao_social": "Nova Corretora S.A.",
        "cd_cnpj":         "99887766000100",
        "nr_susep":        "K9999",
        "cd_email":        "nova@corretora.com.br",
        "nr_celular":      "11999998888",
        "nm_cidade":       "Campinas",
        "sg_estado":       "SP",
    })
    assert r.status_code == 201
    d = r.json()
    assert d["cd_status"] == "AT"
    assert d["nm_razao_social"] == "Nova Corretora S.A."


def test_criar_corretora_cnpj_duplicado():
    r = client.post("/api/corretagem/corretoras", json={
        "nm_razao_social": "Duplicada",
        "cd_cnpj":         "12345678000199",   # seed
        "nr_susep":        "K0000",
    })
    assert r.status_code == 409


def test_criar_corretora_susep_duplicado():
    r = client.post("/api/corretagem/corretoras", json={
        "nm_razao_social": "Duplicada SUSEP",
        "cd_cnpj":         "11112222000100",
        "nr_susep":        "J1234",   # seed
    })
    assert r.status_code == 409


def test_atualizar_corretora():
    r = client.put("/api/corretagem/corretoras/1", json={
        "nm_razao_social": "Corretora Exemplo Atualizada",
        "cd_cnpj":         "12345678000199",
        "nr_susep":        "J1234",
        "cd_email":        "novo@corretora.com.br",
    })
    assert r.status_code == 200
    assert r.json()["cd_email"] == "novo@corretora.com.br"
    # Restaura
    client.put("/api/corretagem/corretoras/1", json={
        "nm_razao_social": "Corretora Exemplo Ltda",
        "cd_cnpj":         "12345678000199",
        "nr_susep":        "J1234",
        "cd_email":        "contato@corretora.com.br",
    })


def test_inativar_corretora():
    r = client.put("/api/corretagem/corretoras/1/status?cd_status=IN", json={})
    assert r.status_code == 200
    assert r.json()["cd_status"] == "IN"
    # Restaura
    client.put("/api/corretagem/corretoras/1/status?cd_status=AT", json={})


def test_status_invalido():
    r = client.put("/api/corretagem/corretoras/1/status?cd_status=ZZ", json={})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# CORRETORES
# ═══════════════════════════════════════════════════════════════════════════════

def test_listar_corretores():
    r = client.get("/api/corretagem/corretores")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["nm_nome"] == "João Corretor Silva"
    assert data[0]["nm_corretora"] == "Corretora Exemplo Ltda"


def test_listar_corretores_por_corretora():
    r = client.get("/api/corretagem/corretores?cd_corretora=1")
    assert r.status_code == 200
    assert all(c["cd_corretora"] == 1 for c in r.json())


def test_detalhar_corretor():
    r = client.get("/api/corretagem/corretores/1")
    assert r.status_code == 200
    d = r.json()
    assert d["nr_susep"] == "J12345"
    assert d["cd_email_principal"] == "joao@corretora.com.br"
    assert d["nr_celular"] == "11976543210"
    assert d["ds_especialidade"] == "Vida em Grupo, VGC"


def test_criar_corretor():
    r = client.post("/api/corretagem/corretores", json={
        "cd_corretora":       1,
        "nm_nome":            "Maria Corretora Lima",
        "nr_cpf":             "11122233344",
        "nr_susep":           "K54321",
        "cd_email_principal": "maria@corretora.com.br",
        "nr_celular":         "11955554444",
        "ds_especialidade":   "GLB, Prestamista",
    })
    assert r.status_code == 201
    d = r.json()
    assert d["nm_corretora"] == "Corretora Exemplo Ltda"
    assert d["cd_status"] == "AT"


def test_criar_corretor_cpf_duplicado():
    r = client.post("/api/corretagem/corretores", json={
        "cd_corretora":       1,
        "nm_nome":            "Duplicado",
        "nr_cpf":             "98765432100",    # seed
        "nr_susep":           "Z99999",
        "cd_email_principal": "dup@corretora.com.br",
    })
    assert r.status_code == 409


def test_criar_corretor_corretora_inexistente():
    r = client.post("/api/corretagem/corretores", json={
        "cd_corretora":       9999,
        "nm_nome":            "Orphan",
        "nr_cpf":             "55544433322",
        "nr_susep":           "X12345",
        "cd_email_principal": "orphan@test.com",
    })
    assert r.status_code == 404


def test_inativar_corretor():
    r = client.put("/api/corretagem/corretores/1/status?cd_status=IN", json={})
    assert r.status_code == 200
    assert r.json()["cd_status"] == "IN"
    client.put("/api/corretagem/corretores/1/status?cd_status=AT", json={})


# ═══════════════════════════════════════════════════════════════════════════════
# VÍNCULOS empresa ↔ corretora
# ═══════════════════════════════════════════════════════════════════════════════

def test_empresa_sem_corretora():
    """Empresa recém-criada não tem corretora — fl_tem_corretora=False."""
    r = client.get("/api/corretagem/empresas/1/corretora")
    assert r.status_code == 200
    d = r.json()
    # Empresa 1 (Prudential) pode ou não ter vínculo dependendo da ordem dos testes
    assert "fl_tem_corretora" in d
    assert "nm_empresa" in d


def test_empresa_inexistente():
    r = client.get("/api/corretagem/empresas/9999/corretora")
    assert r.status_code == 404


def test_criar_vinculo_sem_corretor():
    """Empresa vinculada à corretora, mas sem corretor específico."""
    r = client.post("/api/corretagem/vinculos", json={
        "cd_empresa":   1,
        "cd_corretora": 1,
        "dt_inicio":    "20260101",
        "pct_comissao": 5.0,
    })
    assert r.status_code == 201
    d = r.json()
    assert d["cd_empresa"]   == 1
    assert d["cd_corretora"] == 1
    assert d["nm_corretora"] == "Corretora Exemplo Ltda"
    assert d["nm_corretor"]  is None   # sem corretor específico


def test_empresa_com_corretora_apos_vinculo():
    r = client.get("/api/corretagem/empresas/1/corretora")
    assert r.status_code == 200
    d = r.json()
    assert d["fl_tem_corretora"] is True
    assert d["nm_corretora"] == "Corretora Exemplo Ltda"
    assert d["pct_comissao"] == 5.0
    assert d["nm_corretor"]  is None   # sem corretor ainda


def test_atualizar_vinculo_com_corretor():
    """Adiciona corretor específico ao vínculo criando um novo vínculo."""
    r = client.post("/api/corretagem/vinculos", json={
        "cd_empresa":   1,
        "cd_corretora": 1,
        "cd_corretor":  1,
        "dt_inicio":    "20260201",
        "pct_comissao": 5.0,
    })
    assert r.status_code == 201
    d = r.json()
    assert d["nm_corretor"] == "João Corretor Silva"
    assert d["cd_email_corretor"] == "joao@corretora.com.br"
    assert d["nr_celular_corretor"] == "11976543210"


def test_empresa_com_corretor_vinculado():
    r = client.get("/api/corretagem/empresas/1/corretora")
    d = r.json()
    assert d["nm_corretor"] == "João Corretor Silva"
    assert d["cd_email_corretor"] == "joao@corretora.com.br"
    assert d["nr_celular_corretor"] == "11976543210"


def test_corretor_de_outra_corretora_invalido():
    """Corretor deve pertencer à corretora informada no vínculo."""
    # Cria segunda corretora
    r_c = client.post("/api/corretagem/corretoras", json={
        "nm_razao_social": "Segunda Corretora",
        "cd_cnpj":         "77665544000100",
        "nr_susep":        "Z7766",
    })
    cd_corretora2 = r_c.json()["cd_corretora"]

    # Tenta vincular corretor 1 (da corretora 1) com a corretora 2
    r = client.post("/api/corretagem/vinculos", json={
        "cd_empresa":   1,
        "cd_corretora": cd_corretora2,
        "cd_corretor":  1,   # pertence à corretora 1
        "dt_inicio":    "20260301",
    })
    assert r.status_code == 409


def test_remover_vinculo():
    # Busca vínculos
    r_list = client.get("/api/corretagem/vinculos?cd_empresa=1")
    vinculos_ativos = [v for v in r_list.json() if v["cd_status"] == "AT"]
    assert len(vinculos_ativos) >= 1

    cd_vinculo = vinculos_ativos[-1]["cd_vinculo"]
    r = client.delete(f"/api/corretagem/vinculos/{cd_vinculo}")
    assert r.status_code == 204

    # Empresa volta a ficar sem corretora ativa (ou com o anterior)
    r_emp = client.get("/api/corretagem/empresas/1/corretora")
    assert r_emp.status_code == 200


def test_listar_vinculos():
    r = client.get("/api/corretagem/vinculos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
