"""
Testes da Configuração de Apólice.
Depende de uma apólice criada via fluxo proposta → aceite.
"""
import os
os.environ["BATCH_CONNECTOR"]    = "stub"
os.environ["OTEL_ENABLED"]       = "false"
os.environ["RAG_CHROMA_PATH"]    = "/tmp/lc_chroma_cfg_test"
os.environ["AUTH_SECRET_KEY"]    = "test-secret-key-32chars"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── Setup: cria uma apólice para usar nos testes ──────────────────────────────

NR_PROPOSTA = "2026.PROP.CFG001"
NR_APOLICE  = None   # preenchido pelo test_setup


def _criar_apolice() -> str:
    """Cria proposta, aceita e retorna nr_apolice."""
    client.post("/api/emissao/propostas", json={
        "nr_proposta":      NR_PROPOSTA,
        "cd_empresa":       1,
        "cd_cpf_segurado":  "12345678901",
        "cd_produto":       "VGC",
        "tp_capital":       "F",
        "vl_capital":       200000.0,
        "vl_premio_bruto":  2100.00,
        "dt_proposta":      "20260101",
    })
    r = client.post(f"/api/emissao/propostas/{NR_PROPOSTA}/aceitar", json={
        "nr_proposta": NR_PROPOSTA,
        "tp_aceite":   "AU",
        "id_usuario":  "SYSADM",
    })
    return r.json().get("nr_apolice_gerada", "")


# ── Obtemos o nr_apolice uma vez para toda a suite ────────────────────────────
_nr = _criar_apolice()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG DE FATURAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def test_config_faturamento_inexistente():
    r = client.get(f"/api/emissao/apolices/{_nr}/config/faturamento")
    assert r.status_code == 404


def test_salvar_config_faturamento():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/config/faturamento",
        params={"id_usuario": "SYSADM"},
        json={
            "dia_vencimento":           15,
            "dia_corte":                25,
            "mes_competencia_ini":      "202601",
            "periodicidade":            "MN",
            "fl_repetir_sem_movimento": "S",
            "ds_obs_repeticao":         "Repete fatura anterior se sem movimentação",
            "forma_cobranca":           "BO",
            "fl_nf_eletronica":         "S",
            "cd_email_fatura":          "faturamento@empresa.com.br",
            "cd_email_copia":           "rh@empresa.com.br",
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["dia_vencimento"]           == 15
    assert d["dia_corte"]                == 25
    assert d["fl_repetir_sem_movimento"] == "S"
    assert d["forma_cobranca"]           == "BO"
    assert d["dt_proximo_vencimento"]    == "20260115"


def test_config_faturamento_leitura():
    r = client.get(f"/api/emissao/apolices/{_nr}/config/faturamento")
    assert r.status_code == 200
    assert r.json()["cd_email_fatura"] == "faturamento@empresa.com.br"


def test_mudar_vencimento():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/config/faturamento/vencimento",
        json={
            "dia_vencimento_novo": 20,
            "dt_vigencia":         "20260201",
            "ds_motivo":           "Solicitação do cliente",
            "id_usuario":          "OPERADOR1",
        },
    )
    assert r.status_code == 200
    assert r.json()["dia_vencimento"] == 20


def test_config_apolice_inexistente():
    r = client.get("/api/emissao/apolices/2099.APO.XXXXX/config/faturamento")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# SUBESTIPULANTES
# ═══════════════════════════════════════════════════════════════════════════════

def test_listar_subestipulantes_vazio():
    r = client.get(f"/api/emissao/apolices/{_nr}/subestipulantes")
    assert r.status_code == 200
    assert r.json() == []


def test_adicionar_subestipulante():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/subestipulantes",
        json={
            "cd_cnpj":              "11223344000100",
            "nm_razao_social":      "Filial SP Ltda",
            "nm_nome_reduzido":     "FILIAL SP",
            "cd_email":             "filialsp@empresa.com.br",
            "nr_telefone":          "1133334444",
            "nm_responsavel":       "Ana RH",
            "cd_email_responsavel": "ana@filialsp.com.br",
            "dt_inclusao_apolice":  "20260101",
            "id_usuario":           "SYSADM",
        },
    )
    assert r.status_code == 201
    d = r.json()
    assert d["nm_razao_social"] == "Filial SP Ltda"
    assert d["cd_status"]       == "AT"
    assert d["nr_apolice"]      == _nr


def test_adicionar_segundo_subestipulante():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/subestipulantes",
        json={
            "cd_cnpj":             "55667788000100",
            "nm_razao_social":     "Filial RJ Ltda",
            "dt_inclusao_apolice": "20260101",
            "id_usuario":          "SYSADM",
        },
    )
    assert r.status_code == 201


def test_subestipulante_duplicado():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/subestipulantes",
        json={
            "cd_cnpj":             "11223344000100",   # já existe
            "nm_razao_social":     "Filial SP Dup",
            "dt_inclusao_apolice": "20260101",
            "id_usuario":          "SYSADM",
        },
    )
    assert r.status_code == 409


def test_listar_subestipulantes():
    r = client.get(f"/api/emissao/apolices/{_nr}/subestipulantes")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_cancelar_subestipulante():
    r_list = client.get(f"/api/emissao/apolices/{_nr}/subestipulantes?cd_status=AT")
    cd = r_list.json()[0]["cd_subestipulante"]
    r = client.put(
        f"/api/emissao/apolices/{_nr}/subestipulantes/{cd}/cancelar",
        json={
            "cd_motivo":  "R001",
            "ds_motivo":  "Empresa encerrou atividades",
            "dt_vigencia": "20260201",
            "id_usuario":  "SYSADM",
        },
    )
    assert r.status_code == 200
    assert r.json()["cd_status"] == "CA"


def test_suspender_e_reativar_subestipulante():
    r_list = client.get(f"/api/emissao/apolices/{_nr}/subestipulantes?cd_status=AT")
    ativos = r_list.json()
    assert len(ativos) >= 1
    cd = ativos[0]["cd_subestipulante"]

    # Suspende
    r_sus = client.put(
        f"/api/emissao/apolices/{_nr}/subestipulantes/{cd}/suspender",
        json={
            "cd_motivo":   "S001",
            "ds_motivo":   "Auditoria em andamento",
            "dt_vigencia": "20260201",
            "id_usuario":  "SYSADM",
        },
    )
    assert r_sus.status_code == 200
    assert r_sus.json()["cd_status"] == "SU"

    # Reativa
    r_reat = client.put(
        f"/api/emissao/apolices/{_nr}/subestipulantes/{cd}/reativar",
        params={"id_usuario": "SYSADM"},
    )
    assert r_reat.status_code == 200
    assert r_reat.json()["cd_status"] == "AT"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTATOS
# ═══════════════════════════════════════════════════════════════════════════════

def test_listar_contatos_vazio():
    r = client.get(f"/api/emissao/apolices/{_nr}/contatos")
    assert r.status_code == 200


def test_adicionar_contato_rh():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/contatos",
        json={
            "tp_contato":            "RH",
            "nm_contato":            "Carlos RH",
            "cd_cargo":              "Analista de RH",
            "cd_email":              "carlos.rh@empresa.com.br",
            "nr_telefone":           "1133334455",
            "nr_celular":            "11988887777",
            "fl_recebe_fatura":      "N",
            "fl_recebe_apolice":     "S",
            "fl_recebe_certificado": "S",
        },
    )
    assert r.status_code == 201
    assert r.json()["tp_contato"] == "RH"


def test_adicionar_contato_financeiro():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/contatos",
        json={
            "tp_contato":       "FIN",
            "nm_contato":       "Maria Financeiro",
            "cd_email":         "financeiro@empresa.com.br",
            "fl_recebe_fatura": "S",
        },
    )
    assert r.status_code == 201


def test_atualizar_email_contato():
    r_list = client.get(f"/api/emissao/apolices/{_nr}/contatos")
    cd = r_list.json()[0]["cd_contato"]
    r = client.put(
        f"/api/emissao/apolices/{_nr}/contatos/{cd}",
        json={
            "tp_contato":   "RH",
            "nm_contato":   "Carlos RH Atualizado",
            "cd_email":     "carlos.novo@empresa.com.br",
            "fl_recebe_fatura": "N",
            "fl_recebe_apolice": "S",
            "fl_recebe_certificado": "S",
        },
    )
    assert r.status_code == 200
    assert r.json()["cd_email"] == "carlos.novo@empresa.com.br"


def test_remover_contato():
    r_list = client.get(f"/api/emissao/apolices/{_nr}/contatos")
    contatos = r_list.json()
    assert len(contatos) >= 1
    cd = contatos[-1]["cd_contato"]
    r = client.delete(
        f"/api/emissao/apolices/{_nr}/contatos/{cd}",
        params={"id_usuario": "SYSADM"},
    )
    assert r.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════════
# ENDEREÇO
# ═══════════════════════════════════════════════════════════════════════════════

def test_atualizar_endereco():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/endereco",
        json={
            "ds_logradouro":  "Av. Paulista",
            "nr_numero":      "1000",
            "ds_complemento": "10º andar",
            "nm_bairro":      "Bela Vista",
            "nm_cidade":      "São Paulo",
            "sg_estado":      "SP",
            "cd_cep":         "01310100",
            "id_usuario":     "SYSADM",
        },
    )
    assert r.status_code == 200
    assert "Av. Paulista" in r.json()["ds_endereco"]


# ═══════════════════════════════════════════════════════════════════════════════
# OPERAÇÕES ESPECIAIS
# ═══════════════════════════════════════════════════════════════════════════════

def test_alterar_produto():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/produto",
        json={
            "cd_produto_novo": "GLB",
            "dt_vigencia":     "20260201",
            "ds_motivo":       "Mudança de produto solicitada pelo cliente",
            "id_usuario":      "SYSADM",
        },
    )
    assert r.status_code == 200
    assert r.json()["cd_produto_novo"] == "GLB"
    assert r.json()["cd_produto_anterior"] == "VGC"


def test_alterar_produto_igual():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/produto",
        json={
            "cd_produto_novo": "GLB",
            "dt_vigencia":     "20260201",
            "ds_motivo":       "Sem mudança",
            "id_usuario":      "SYSADM",
        },
    )
    assert r.status_code == 409


def test_transferencia_cnpj():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/transferir-cnpj",
        json={
            "cd_cnpj_novo":          "99887766000100",
            "nm_razao_social_novo":  "Empresa Nova Razão Social S.A.",
            "dt_vigencia":           "20260301",
            "ds_motivo":             "Fusão societária",
            "id_usuario":            "SYSADM",
        },
    )
    assert r.status_code == 200
    assert r.json()["cd_cnpj_novo"] == "99887766000100"


def test_renovar_apolice():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/renovar",
        json={
            "dt_inicio_nova_vigencia": "20270101",
            "dt_fim_nova_vigencia":    "20271231",
            "fl_manter_config":        "S",
            "ds_observacao":           "Renovação anual",
            "id_usuario":              "SYSADM",
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["nr_apolice_origem"] == _nr
    assert d["nr_apolice_nova"] != _nr
    assert d["fl_config_copiada"] == "S"


def test_renovar_vigencia_invalida():
    r = client.post(
        f"/api/emissao/apolices/{_nr}/renovar",
        json={
            "dt_inicio_nova_vigencia": "20271231",
            "dt_fim_nova_vigencia":    "20270101",   # fim < início
            "fl_manter_config":        "N",
            "id_usuario":              "SYSADM",
        },
    )
    assert r.status_code == 422


def test_cancelar_apolice():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/cancelar",
        json={
            "cd_motivo":          "C001",
            "ds_motivo":          "Cancelamento solicitado pelo estipulante",
            "dt_cancelamento":    "20260630",
            "fl_devolver_premio": "S",
            "id_usuario":         "SYSADM",
        },
    )
    assert r.status_code == 200
    assert r.json()["cd_status"] == "CA"
    assert r.json()["fl_devolucao_premio"] == "S"


def test_cancelar_apolice_ja_cancelada():
    r = client.put(
        f"/api/emissao/apolices/{_nr}/cancelar",
        json={
            "cd_motivo":       "C001",
            "ds_motivo":       "Duplicado",
            "dt_cancelamento": "20260630",
            "fl_devolver_premio": "N",
            "id_usuario":      "SYSADM",
        },
    )
    assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# HISTÓRICO
# ═══════════════════════════════════════════════════════════════════════════════

def test_historico_completo():
    r = client.get(f"/api/emissao/apolices/{_nr}/historico")
    assert r.status_code == 200
    historico = r.json()
    assert len(historico) > 0
    tipos = {h["tp_acao"] for h in historico}
    # Deve ter registros de várias operações feitas nos testes acima
    assert "CONFIG_FATURAMENTO"  in tipos
    assert "MUDANCA_VENCIMENTO"  in tipos
    assert "SUBESTIP_INCLUS"     in tipos
    assert "CANCELAMENTO"        in tipos
    assert "PRODUTO_ALTERADO"    in tipos
    assert "TRANSF_CNPJ"         in tipos
    assert "RENOVACAO"           in tipos


def test_historico_filtrado_por_tipo():
    r = client.get(f"/api/emissao/apolices/{_nr}/historico?tp_acao=CANCELAMENTO")
    assert r.status_code == 200
    for h in r.json():
        assert h["tp_acao"] == "CANCELAMENTO"
