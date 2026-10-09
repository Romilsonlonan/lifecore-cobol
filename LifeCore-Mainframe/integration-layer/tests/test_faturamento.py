"""
Testes — Faturamento, Endossos, Coberturas, Revalidação e Taxas IPCA
Cobertura de todos os endpoints novos:
  /api/emissao/apolices/{nr_apolice}/faturamento
  /api/emissao/apolices/{nr_apolice}/endossos
  /api/emissao/apolices/{nr_apolice}/detalhes
  /api/emissao/apolices/{nr_apolice}/coberturas
  /api/emissao/apolices/{nr_apolice}/coberturas/{cpf}/revalidar
  /api/emissao/apolices/{nr_apolice}/coberturas/{cpf}/registrar-inadimplencia
  /api/emissao/taxas-ipca
"""

import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

import uuid as _uuid

CPF_SEG1 = "11111111111"
CPF_SEG2 = "22222222222"
NR_APOLICE: str = ""  # preenchido nos fixtures


def _criar_apolice(suffix: str = "") -> str:
    """Cria proposta única → aceita → retorna nr_apolice."""
    nr_prop = f"2026.PROP.{suffix or _uuid.uuid4().hex[:8].upper()}"
    r = client.post(
        "/api/emissao/propostas",
        json={
            "nr_proposta": nr_prop,
            "cd_empresa": 1,
            "cd_cpf_segurado": CPF_SEG1,
            "cd_produto": "VGC",
            "tp_capital": "F",
            "vl_capital": 200000.00,
            "dt_proposta": "20260101",
        },
    )
    assert r.status_code == 201, r.text

    r2 = client.post(
        f"/api/emissao/propostas/{nr_prop}/aceitar",
        json={
            "nr_proposta": nr_prop,
            "tp_aceite": "MA",
            "id_usuario": "USR001",
        },
    )
    assert r2.status_code == 200, r2.text
    return r2.json()["nr_apolice_gerada"]


# ── TAXAS IPCA ────────────────────────────────────────────────────────────────


class TestTaxasIPCA:
    def test_listar_taxas_seed(self):
        """As taxas seed devem estar presentes."""
        r = client.get("/api/emissao/taxas-ipca")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 7, "Seed deveria ter 7 taxas (202501-202507)"

    def test_listar_taxas_vigente_filter(self):
        r = client.get("/api/emissao/taxas-ipca?fl_vigente=true")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["fl_vigente"] is True

    def test_consultar_taxa_existente(self):
        r = client.get("/api/emissao/taxas-ipca/202501")
        assert r.status_code == 200
        data = r.json()
        assert data["cd_competencia"] == "202501"
        assert data["vl_taxa_ipca"] == pytest.approx(0.16)

    def test_consultar_taxa_inexistente(self):
        r = client.get("/api/emissao/taxas-ipca/199901")
        assert r.status_code == 404

    def test_cadastrar_nova_taxa(self):
        r = client.post(
            "/api/emissao/taxas-ipca",
            json={
                "cd_competencia": "202508",
                "vl_taxa_ipca": 0.44,
                "vl_taxa_acumulada": 4.61,
                "dt_divulgacao": "20250912",
                "ds_fonte": "IBGE/IPCA",
                "fl_vigente": True,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["cd_competencia"] == "202508"
        assert data["fl_vigente"] is True

    def test_cadastrar_taxa_duplicada(self):
        r = client.post(
            "/api/emissao/taxas-ipca",
            json={
                "cd_competencia": "202508",
                "vl_taxa_ipca": 0.50,
                "vl_taxa_acumulada": 4.70,
                "dt_divulgacao": "20250912",
                "fl_vigente": True,
            },
        )
        assert r.status_code == 409


# ── ENDOSSOS ──────────────────────────────────────────────────────────────────


class TestEndossos:
    @pytest.fixture(autouse=True)
    def setup(self):
        global NR_APOLICE
        NR_APOLICE = _criar_apolice()

    def test_incluir_segurado(self):
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["cd_status"] == "PR"
        assert data["vl_capital_calculado"] is not None
        assert data["vl_premio_calculado"] is not None

    def test_incluir_segurado_duplicado(self):
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        r2 = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        assert r2.status_code == 409

    def test_excluir_segurado(self):
        # Inclui primeiro
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "EXC",
                "dt_inicio_vigencia": "20260301",
                "id_usuario": "USR001",
                "cd_motivo": "DEMI",
                "ds_observacao": "Demissão voluntária.",
            },
        )
        assert r.status_code == 201
        assert r.json()["cd_status"] == "PR"

    def test_alterar_capital(self):
        # Inclui
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "CAP",
                "dt_inicio_vigencia": "20260301",
                "vl_capital": 200000.00,
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 201
        assert r.json()["vl_capital_calculado"] == pytest.approx(
            200000 * 1.0044, rel=0.01
        )

    def test_listar_endossos(self):
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/endossos")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_detalhar_endosso(self):
        # Inclui e pega o nr_endosso
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "MARIA SILVA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 150000.00,
                "id_usuario": "USR001",
            },
        )
        nr = r.json()["nr_endosso"]
        r2 = client.get(f"/api/emissao/apolices/{NR_APOLICE}/endossos/{nr}")
        assert r2.status_code == 200
        assert r2.json()["nr_endosso"] == nr

    def test_endosso_apolice_inexistente(self):
        r = client.post(
            "/api/emissao/apolices/NAOEXISTE/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "TESTE",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 404


# ── FATURAMENTO ───────────────────────────────────────────────────────────────


class TestFaturamento:
    @pytest.fixture(autouse=True)
    def setup(self):
        global NR_APOLICE
        NR_APOLICE = _criar_apolice()

    def test_gerar_fatura_sem_coberturas(self):
        """Gera fatura usando capital da apólice diretamente."""
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202606",
                "dt_vencimento": "20260610",
                "forma_cobranca": "BO",
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["nr_apolice"] == NR_APOLICE
        assert data["nr_segurados"] == 1
        assert data["vl_total_bruto"] > 0
        assert data["vl_reajuste_ipca"] >= 0
        assert len(data["itens"]) == 1

    def test_gerar_fatura_com_coberturas(self):
        """Inclui segurado via endosso e gera fatura com múltiplos itens."""
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "PEDRO SANTOS",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 100000.00,
                "id_usuario": "USR001",
            },
        )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202607",
                "dt_vencimento": "20260710",
                "forma_cobranca": "CC",
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["nr_segurados"] >= 1
        # Itens da fatura devem ter IPCA aplicado
        for item in data["itens"]:
            assert item["vl_capital_coberto"] > 0
            assert item["vl_premio_bruto"] > 0

    def test_fatura_duplicada_rejeitada(self):
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202608",
                "dt_vencimento": "20260810",
                "forma_cobranca": "BO",
                "id_usuario": "USR001",
            },
        )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202608",
                "dt_vencimento": "20260810",
                "forma_cobranca": "BO",
                "id_usuario": "USR001",
            },
        )
        assert r.status_code == 409

    def test_listar_faturas(self):
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202609",
                "dt_vencimento": "20260910",
                "forma_cobranca": "PI",
                "id_usuario": "USR001",
            },
        )
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/faturamento")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_detalhar_fatura(self):
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/faturamento",
            json={
                "nr_apolice": NR_APOLICE,
                "cd_competencia": "202610",
                "dt_vencimento": "20261010",
                "forma_cobranca": "DB",
                "id_usuario": "USR001",
            },
        )
        nr_fat = r.json()["nr_fatura"]
        r2 = client.get(f"/api/emissao/apolices/{NR_APOLICE}/faturamento/{nr_fat}")
        assert r2.status_code == 200
        assert r2.json()["nr_fatura"] == nr_fat


# ── CONSULTA DETALHADA ────────────────────────────────────────────────────────


class TestConsultaApolice:
    @pytest.fixture(autouse=True)
    def setup(self):
        global NR_APOLICE
        NR_APOLICE = _criar_apolice()

    def test_detalhe_completo(self):
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/detalhes")
        assert r.status_code == 200
        data = r.json()
        assert data["nr_apolice"] == NR_APOLICE
        assert "coberturas" in data
        assert "ultimas_faturas" in data
        assert data["nm_produto"] == "Vida em Grupo Coletivo"
        assert data["taxa_ipca_vigente"] is not None

    def test_listar_coberturas_vazio(self):
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/coberturas")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_listar_coberturas_apos_endosso(self):
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "ANA COSTA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 120000.00,
                "id_usuario": "USR001",
            },
        )
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/coberturas")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_detalhar_cobertura(self):
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "ANA COSTA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260201",
                "vl_capital": 120000.00,
                "id_usuario": "USR001",
            },
        )
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}")
        assert r.status_code == 200
        d = r.json()
        assert d["cd_cpf_segurado"] == CPF_SEG2
        assert d["vl_capital_atual"] > 0

    def test_detalhe_inexistente(self):
        r = client.get("/api/emissao/apolices/NAOEXISTE/detalhes")
        assert r.status_code == 404


# ── INADIMPLÊNCIA e REVALIDAÇÃO ───────────────────────────────────────────────


class TestInadimplenciaRevalidacao:
    @pytest.fixture(autouse=True)
    def setup(self):
        global NR_APOLICE
        NR_APOLICE = _criar_apolice()
        # Inclui segurado
        client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/endossos",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "nm_segurado": "JOSE LIMA",
                "tp_endosso": "INC",
                "dt_inicio_vigencia": "20260101",
                "vl_capital": 80000.00,
                "id_usuario": "USR001",
            },
        )

    def test_grace_period_3_meses(self):
        """3 meses sem pagamento → cobertura ATIVA (grace period)."""
        for _ in range(3):
            r = client.post(
                f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/registrar-inadimplencia"
            )
            assert r.status_code == 200
            assert r.json()["cd_status_cobertura"] == "AT"

    def test_sem_cobertura_apos_4_meses(self):
        """4 meses → SEM_COBERTURA."""
        for _ in range(4):
            client.post(
                f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/registrar-inadimplencia"
            )
        r = client.get(f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}")
        assert r.status_code == 200
        assert r.json()["cd_status_cobertura"] == "SC"

    def test_revalidacao_sem_retroativo(self):
        """Revalidação após >3 meses: sem retroativo, nova vigência."""
        for _ in range(4):
            client.post(
                f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/registrar-inadimplencia"
            )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/revalidar",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "dt_reativacao": "20261001",
                "fl_cobrar_retroativo": False,
                "id_usuario": "USR001",
                "ds_justificativa": "Regularização de pagamento.",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["cd_status_novo"] == "AT"
        assert data["fl_cobertura_retroativa"] is False
        assert data["vl_premio_devido"] == 0.0
        assert data["nr_meses_inadimplente"] == 4

    def test_revalidacao_grace_period(self):
        """Revalidação em grace period (2 meses): apenas zera contador."""
        for _ in range(2):
            client.post(
                f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/registrar-inadimplencia"
            )
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/revalidar",
            json={
                "cd_cpf_segurado": CPF_SEG2,
                "dt_reativacao": "20260901",
                "fl_cobrar_retroativo": False,
                "id_usuario": "USR001",
                "ds_justificativa": "Regularização antecipada.",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["cd_status_anterior"] == "AT"
        assert data["cd_status_novo"] == "AT"
        assert data["vl_premio_devido"] == 0.0

    def test_revalidacao_cpf_mismatch(self):
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/coberturas/{CPF_SEG2}/revalidar",
            json={
                "cd_cpf_segurado": "99999999999",  # diferente do path
                "dt_reativacao": "20261001",
                "fl_cobrar_retroativo": False,
                "id_usuario": "USR001",
                "ds_justificativa": "Teste.",
            },
        )
        assert r.status_code == 400

    def test_inadimplencia_segurado_inexistente(self):
        r = client.post(
            f"/api/emissao/apolices/{NR_APOLICE}/coberturas/99999999999/registrar-inadimplencia"
        )
        assert r.status_code == 404
