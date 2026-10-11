"""
Testes de integração da Integration Layer — v2
Cobre: health, importação/batch (legado), cadastros, emissão,
       sinistro, ECM, impressão, cosseguro, pessoas e painel.
Não requer COBOL instalado — usa batch_connector = "stub".
"""

import os
from datetime import UTC, datetime

os.environ["BATCH_CONNECTOR"] = "stub"
os.environ["DATA_INPUT_DIR"] = "/tmp/lifecore_test/INPUT"
os.environ["DATA_OUTPUT_DIR"] = "/tmp/lifecore_test/OUTPUT"
os.environ["DATA_QUARANTINE_DIR"] = "/tmp/lifecore_test/QUARANTINE"

import pytest
from app.api.cadastros import empresa as empresa_api
from app.main import app
from app.repositories.empresa_db2 import Db2Unavailable
from app.schemas.lifecore import StatusGeralEnum, TipoEmpresaEnum
from fastapi.testclient import TestClient

client = TestClient(app)


class _FakeEmpresaRepository:
    def __init__(self):
        self.rows = {
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
                "ts_inclusao": datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC),
            }
        }

    def listar(self, status=None):
        rows = list(self.rows.values())
        return [row for row in rows if status is None or row["cd_status"] == status]

    def obter(self, cd_empresa):
        from app.repositories.empresa_db2 import EmpresaNotFound

        if cd_empresa not in self.rows:
            raise EmpresaNotFound
        return self.rows[cd_empresa]

    def criar(self, payload, usuario):
        from app.repositories.empresa_db2 import EmpresaAlreadyExists

        if any(
            row["cd_cnpj"] == payload.cd_cnpj or row["nr_codigo"] == payload.nr_codigo
            for row in self.rows.values()
        ):
            raise EmpresaAlreadyExists("Código ou CNPJ já cadastrado.")
        cd_empresa = max(self.rows) + 1
        row = {
            "cd_empresa": cd_empresa,
            **payload.model_dump(),
            "cd_status": StatusGeralEnum.ATIVO,
            "dt_inclusao": "20261005",
            "ts_inclusao": datetime(2026, 10, 5, tzinfo=UTC),
        }
        self.rows[cd_empresa] = row
        return row

    def alterar_status(self, cd_empresa, status):
        row = self.obter(cd_empresa)
        row["cd_status"] = status
        return row


@pytest.fixture(autouse=True)
def fake_empresa_repository(monkeypatch):
    monkeypatch.setattr(empresa_api, "empresa_repository", _FakeEmpresaRepository())


# ── CSV de teste ─────────────────────────────────────────────────────────────

CSV_VALIDO = (
    "numero_apolice,produto,cnpj_estipulante,cpf_segurado,nome_segurado,"
    "vigencia_ini,vigencia_fim,tipo_capital,capital_segurado,salario_base,"
    "fator_multiplicador,premio_liquido,premio_bruto,iof,forma_pagamento,periodicidade\n"
    "APO000000001,VGC,12345678000195,12345678901,JOSE DA SILVA,"
    "20240101,20251231,F,100000.00,,,1050.00,1055.25,5.25,BO,MN\n"
    "APO000000002,GLB,98765432000100,98765432100,MARIA SOUZA,"
    "20240101,20251231,M,0,5000.00,20,,105000.00,0,,MN\n"
)

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "2.1.0"


# ═══════════════════════════════════════════════════════════════════════════════
# LEGADO — Importação + Batch
# ═══════════════════════════════════════════════════════════════════════════════


def test_importar_csv_valido():
    r = client.post(
        "/api/apolices/importar",
        files={"arquivo": ("apolices.csv", CSV_VALIDO.encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_registros"] == 2
    assert data["job_id"] is not None
    assert data["status"] == "PENDENTE"


def test_importar_extensao_invalida():
    r = client.post(
        "/api/apolices/importar",
        files={"arquivo": ("apolices.txt", b"x", "text/plain")},
    )
    assert r.status_code == 422
    assert "Formato" in r.json()["detail"]


def test_importar_arquivo_vazio():
    r = client.post(
        "/api/apolices/importar",
        files={"arquivo": ("vazio.csv", b"", "text/csv")},
    )
    assert r.status_code == 422


def test_status_job_nao_encontrado():
    r = client.get("/api/jobs/INEXISTENTE/status")
    assert r.status_code == 404


def test_status_job_apos_importar():
    r_imp = client.post(
        "/api/apolices/importar",
        files={"arquivo": ("apolices.csv", CSV_VALIDO.encode(), "text/csv")},
    )
    assert r_imp.status_code == 200
    job_id = r_imp.json()["job_id"]
    r_st = client.get(f"/api/jobs/{job_id}/status")
    assert r_st.status_code == 200
    assert r_st.json()["status"] in ("PENDENTE", "EXECUTANDO", "CONCLUIDO", "ERRO")


def test_resultado_job_inexistente():
    r = client.get("/api/apolices/resultado/XYZXYZ")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# CADASTROS — Empresa
# ═══════════════════════════════════════════════════════════════════════════════


def test_listar_empresas():
    r = client.get("/api/cadastros/empresas", headers=_admin_headers())
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["nm_razao_social"] == "Prudential do Brasil Seguros de Vida S.A."


def test_detalhar_empresa_existente():
    r = client.get("/api/cadastros/empresas/1", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["cd_empresa"] == 1


def test_detalhar_empresa_inexistente():
    r = client.get("/api/cadastros/empresas/9999", headers=_admin_headers())
    assert r.status_code == 404


def _admin_headers():
    response = client.post(
        "/auth/login",
        json={
            "cd_email": "admin@lifecore.com.br",
            "ds_senha": "lifecore@2026",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_listar_empresas_exige_autenticacao():
    response = client.get("/api/cadastros/empresas")
    assert response.status_code == 401


def test_criar_empresa_exige_administrador():
    response = client.post(
        "/api/cadastros/empresas",
        json={
            "nr_codigo": "000002",
            "nm_razao_social": "Estipulante Teste Ltda",
            "cd_cnpj": "99887766000100",
            "tp_empresa": "ES",
        },
    )
    assert response.status_code == 401


def test_empresa_indisponivel_sem_db2():
    class UnavailableRepository:
        def listar(self, status=None):
            raise Db2Unavailable("DB2_DSN não foi configurado.")

    empresa_api.empresa_repository = UnavailableRepository()
    response = client.get("/api/cadastros/empresas", headers=_admin_headers())
    assert response.status_code == 503
    assert response.json()["detail"] == "DB2_DSN não foi configurado."


def test_alterar_status_empresa_exige_administrador():
    response = client.put("/api/cadastros/empresas/1/status", params={"cd_status": "IN"})
    assert response.status_code == 401


def test_criar_empresa():
    payload = {
        "nr_codigo": "000002",
        "nm_razao_social": "Corretora Teste Ltda",
        "cd_cnpj": "99887766000100",
        "tp_empresa": "CO",
    }
    r = client.post("/api/cadastros/empresas", json=payload, headers=_admin_headers())
    assert r.status_code == 201
    data = r.json()
    assert data["cd_empresa"] >= 2
    assert data["cd_status"] == "AT"


def test_criar_empresa_cnpj_duplicado():
    payload = {
        "nr_codigo": "000099",
        "nm_razao_social": "Duplicada",
        "cd_cnpj": "51990695000137",  # CNPJ da Prudential (seed)
        "tp_empresa": "SE",
    }
    r = client.post("/api/cadastros/empresas", json=payload, headers=_admin_headers())
    assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# CADASTROS — Congênere
# ═══════════════════════════════════════════════════════════════════════════════


def test_listar_congeneres():
    r = client.get("/api/cadastros/congeneres")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_criar_e_deletar_congenere():
    payload = {
        "nr_susep": "9999",
        "nm_congenere": "Teste RE",
        "tp_pessoa": "PJ",
        "cd_cnpj_cpf": "11223344000100",
    }
    r_create = client.post("/api/cadastros/congeneres", json=payload)
    assert r_create.status_code == 201
    cd = r_create.json()["cd_congenere"]

    r_del = client.delete(f"/api/cadastros/congeneres/{cd}")
    assert r_del.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════════
# CADASTROS — Segurado
# ═══════════════════════════════════════════════════════════════════════════════


def test_criar_segurado_cpf_invalido():
    payload = {
        "cd_cpf": "00000000000",
        "nm_segurado": "INVALIDO",
        "dt_nascimento": "19900101",
        "cd_sexo": "M",
        "cd_empresa": 1,
    }
    r = client.post("/api/cadastros/segurados", json=payload)
    assert r.status_code == 422


def test_listar_segurados():
    r = client.get("/api/cadastros/segurados")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ═══════════════════════════════════════════════════════════════════════════════
# EMISSÃO — Proposta → Aceite → Apólice
# ═══════════════════════════════════════════════════════════════════════════════

_NR_PROPOSTA = "2026.PROP.TEST01"


def test_criar_proposta():
    payload = {
        "nr_proposta": _NR_PROPOSTA,
        "cd_empresa": 1,
        "cd_cpf_segurado": "12345678901",
        "cd_produto": "VGC",
        "tp_capital": "F",
        "vl_capital": 100000.00,
        "vl_premio_bruto": 1055.25,
        "dt_proposta": "20260101",
    }
    r = client.post("/api/emissao/propostas", json=payload)
    assert r.status_code == 201
    assert r.json()["cd_status"] == "AN"


def test_criar_proposta_duplicada():
    payload = {
        "nr_proposta": _NR_PROPOSTA,
        "cd_empresa": 1,
        "cd_cpf_segurado": "12345678901",
        "cd_produto": "VGC",
        "tp_capital": "F",
        "vl_capital": 100000.00,
        "dt_proposta": "20260101",
    }
    r = client.post("/api/emissao/propostas", json=payload)
    assert r.status_code == 409


def test_aceitar_proposta():
    payload = {
        "nr_proposta": _NR_PROPOSTA,
        "tp_aceite": "AU",
        "id_usuario": "SYSADM",
    }
    r = client.post(f"/api/emissao/propostas/{_NR_PROPOSTA}/aceitar", json=payload)
    assert r.status_code == 200
    assert r.json()["cd_status"] == "AC"
    assert "nr_apolice_gerada" in r.json()


def test_listar_apolices_apos_aceite():
    r = client.get("/api/emissao/apolices")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["cd_status"] == "AT"


def test_recusar_proposta_ja_aceita():
    payload = {
        "nr_proposta": _NR_PROPOSTA,
        "cd_motivo": "R001",
        "ds_motivo": "Documentação incompleta",
        "id_usuario": "SYSADM",
    }
    r = client.post(f"/api/emissao/propostas/{_NR_PROPOSTA}/recusar", json=payload)
    assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# SINISTRO
# ═══════════════════════════════════════════════════════════════════════════════

_NR_SINISTRO = "2026.SIN.TEST01"


def test_abrir_sinistro():
    # Limpa estado para garantir idempotência entre runs do pytest
    from app.api.sinistro import sinistro as _sin_mod

    _sin_mod._DB.pop(_NR_SINISTRO, None)

    payload = {
        "nr_sinistro": _NR_SINISTRO,
        "nr_apolice": "2026.APO.000001",
        "cd_cpf_segurado": "12345678901",
        "cd_empresa": 1,
        "cd_tipo_evento": "MORT",
        "dt_evento": "20260115",
        "dt_abertura": "20260116",
        "id_usuario_incl": "SYSADM",
    }
    r = client.post("/api/sinistro", json=payload)
    assert r.status_code == 201
    assert r.json()["cd_status"] == "AB"


def test_abrir_sinistro_duplicado():
    payload = {
        "nr_sinistro": _NR_SINISTRO,
        "nr_apolice": "2026.APO.000001",
        "cd_cpf_segurado": "12345678901",
        "cd_empresa": 1,
        "cd_tipo_evento": "MORT",
        "dt_evento": "20260115",
        "dt_abertura": "20260116",
        "id_usuario_incl": "SYSADM",
    }
    r = client.post("/api/sinistro", json=payload)
    assert r.status_code == 409


def test_analisar_sinistro():
    payload = {
        "parecer": "FAVORAVEL",
        "ds_parecer": "Documentação completa",
        "vl_indenizacao": 100000.00,
        "id_usuario": "ANALISTA1",
    }
    r = client.put(f"/api/sinistro/{_NR_SINISTRO}/analisar", json=payload)
    assert r.status_code == 200
    assert r.json()["cd_status"] == "AN"


def test_pagar_sinistro():
    payload = {
        "vl_pago": 100000.00,
        "dt_pagamento": "20260120",
        "nr_doc_banco": "DOC20260120001",
        "id_usuario": "FINANCEIRO",
    }
    r = client.put(f"/api/sinistro/{_NR_SINISTRO}/pagar", json=payload)
    assert r.status_code == 200
    assert r.json()["vl_pago"] == 100000.00


def test_encerrar_sinistro():
    payload = {"ds_motivo": "Indenização paga", "id_usuario": "SYSADM"}
    r = client.put(f"/api/sinistro/{_NR_SINISTRO}/encerrar", json=payload)
    assert r.status_code == 200
    assert r.json()["cd_status"] == "EN"


# ═══════════════════════════════════════════════════════════════════════════════
# SINISTRO — ECM
# ═══════════════════════════════════════════════════════════════════════════════


def test_anexar_e_listar_documento_ecm():
    payload = {
        "nm_grupo": "SIN",
        "nm_tipo": "Certidão Óbito",
        "nm_arquivo": "certidao_obito_12345678901.pdf",
        "id_usuario_incl": "ANALISTA1",
    }
    r_add = client.post(f"/api/sinistro/{_NR_SINISTRO}/documentos", json=payload)
    assert r_add.status_code == 201
    cd_doc = r_add.json()["cd_doc_ecm"]

    r_list = client.get(f"/api/sinistro/{_NR_SINISTRO}/documentos")
    assert r_list.status_code == 200
    assert any(d["cd_doc_ecm"] == cd_doc for d in r_list.json())


def test_grupo_ecm_invalido():
    payload = {
        "nm_grupo": "XXX",
        "nm_tipo": "Algo",
        "nm_arquivo": "arquivo.pdf",
        "id_usuario_incl": "USER",
    }
    r = client.post(f"/api/sinistro/{_NR_SINISTRO}/documentos", json=payload)
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# IMPRESSÃO
# ═══════════════════════════════════════════════════════════════════════════════


def test_listar_controles_impressao():
    r = client.get("/api/impressao/controle")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_criar_e_fechar_controle():
    from datetime import datetime

    data_hoje = datetime.today().strftime("%Y%m%d")
    payload = {
        "cd_empresa": 1,
        "nm_modulo": "Sinistro",
        "dt_movimento_contabil": "20260201",
        "nr_pendentes": 5,
        "nr_gerados": 95,
        "nr_nao_gerados": 0,
    }
    r_create = client.post("/api/impressao/controle", json=payload)
    assert r_create.status_code == 201
    cd = r_create.json()["cd_controle"]

    r_fechar = client.put(f"/api/impressao/controle/{cd}/fechar?id_usuario=SYSADM")
    assert r_fechar.status_code == 200
    assert r_fechar.json()["fl_fechado"] == "S"


# ═══════════════════════════════════════════════════════════════════════════════
# COSSEGURO
# ═══════════════════════════════════════════════════════════════════════════════


def test_criar_e_confirmar_cosseguro():
    payload = {
        "nr_apolice": "2026.APO.000001",
        "cd_congenere_lider": 1,
        "cd_congenere_segui": 2,
        "pct_participacao": 30.0,
        "vl_capital_cedido": 30000.00,
        "vl_premio_cedido": 315.00,
        "dt_inicio_vigencia": "20260101",
        "dt_fim_vigencia": "20261231",
    }
    r_create = client.post("/api/cosseguro/participacoes", json=payload)
    assert r_create.status_code == 201
    cd = r_create.json()["cd_cosseguro"]
    assert r_create.json()["cd_status"] == "PENDENTE"

    r_conf = client.put(
        f"/api/cosseguro/participacoes/{cd}/confirmar",
        json={"id_usuario": "SYSADM"},
    )
    assert r_conf.status_code == 200
    assert r_conf.json()["cd_status"] == "CONFIRMADO"


def test_cosseguro_vigencia_invalida():
    payload = {
        "nr_apolice": "2026.APO.ZZZZZ",
        "cd_congenere_lider": 1,
        "cd_congenere_segui": 3,
        "pct_participacao": 20.0,
        "vl_capital_cedido": 20000.00,
        "vl_premio_cedido": 200.00,
        "dt_inicio_vigencia": "20261231",
        "dt_fim_vigencia": "20260101",  # menor que início
    }
    r = client.post("/api/cosseguro/participacoes", json=payload)
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# PESSOAS
# ═══════════════════════════════════════════════════════════════════════════════


def test_listar_pessoas():
    r = client.get("/api/pessoas")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_criar_pessoa():
    payload = {
        "tp_pessoa": "PF",
        "cd_cpf_cnpj": "55566677788",
        "nm_pessoa": "CORRETOR NOVO",
        "cd_tipo_relacao": "COR",
    }
    r = client.post("/api/pessoas", json=payload)
    assert r.status_code == 201
    assert r.json()["nm_tipo_relacao"] == "Corretor"


def test_criar_pessoa_tipo_invalido():
    payload = {
        "tp_pessoa": "PF",
        "cd_cpf_cnpj": "11100011100",
        "nm_pessoa": "INVALIDO",
        "cd_tipo_relacao": "ZZZ",
    }
    r = client.post("/api/pessoas", json=payload)
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL
# ═══════════════════════════════════════════════════════════════════════════════


def test_painel():
    r = client.get("/api/painel")
    assert r.status_code == 200
    data = r.json()
    assert "kpis" in data
    assert "pipeline_aceitacao" in data
    assert "ultimas_acoes" in data
    assert "impressoes_hoje" in data
    assert len(data["kpis"]) == 4
    titulos = [k["titulo"] for k in data["kpis"]]
    assert "Apólices Vigentes" in titulos
    assert "Sinistros Abertos" in titulos
    assert "Segurados Ativos" in titulos
    # Com Supabase ativo: "Apólices Canceladas"; fallback in-memory: "Prêmio Mês (R$)"
    assert "Apólices Canceladas" in titulos or "Prêmio Mês (R$)" in titulos


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSOR (legado)
# ═══════════════════════════════════════════════════════════════════════════════


def test_conversor_csv_para_flat():
    from app.services.conversor import build_flat_file, parse_csv

    apolices = parse_csv(CSV_VALIDO.encode())
    assert len(apolices) == 2
    flat = build_flat_file(apolices)
    linhas = [l for l in flat.splitlines() if l]
    assert len(linhas) == 4
    assert linhas[0].startswith("H0")
    assert linhas[1].startswith("D1")
    assert linhas[3].startswith("T9")
    for linha in linhas:
        assert len(linha) == 300


def test_conversor_registro_300_chars():
    from app.services.conversor import apolice_to_fixed, parse_csv

    apolices = parse_csv(CSV_VALIDO.encode())
    linha = apolice_to_fixed(apolices[0], 1)
    assert len(linha) == 300


def test_conversor_json():
    import json

    from app.services.conversor import parse_json

    dados = [
        {
            "numero_apolice": "APO000000003",
            "produto": "VGC",
            "cnpj_estipulante": "12345678000195",
            "cpf_segurado": "11122233344",
            "nome_segurado": "CARLOS SILVA",
            "vigencia_ini": "20240101",
            "vigencia_fim": "20251231",
            "tipo_capital": "F",
            "capital_segurado": 50000.0,
            "premio_liquido": 500.0,
            "premio_bruto": 502.5,
            "forma_pagamento": "CC",
            "periodicidade": "MN",
        }
    ]
    apolices = parse_json(json.dumps(dados).encode())
    assert len(apolices) == 1
    assert apolices[0].numero_apolice == "APO000000003"
