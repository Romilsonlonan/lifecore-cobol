"""
Testes — Importação de Movimentação de Segurados via Planilha
Cobertura de:
  POST /api/emissao/apolices/{nr_apolice}/movimentacao/importar
  GET  /api/emissao/movimentacao/template
  GET  /api/emissao/movimentacao/template.xlsx
  + serviço movimentacao_segurados (unitários)
"""
import io
import csv
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.movimentacao_segurados import (
    processar_movimentacao,
    _normalizar_col,
    _limpar_cpf,
    _parsear_data,
    _parsear_valor,
    _tp_movimentacao,
    _mapear_colunas,
)

client = TestClient(app)

# ── CPFs válidos (dígito verificador correto) ─────────────────────────────────
CPF_V1  = "11144477735"   # 111.444.777-35
CPF_V2  = "52998224725"   # 529.982.247-25
CPF_V3  = "12345678577"   # 123.456.785-77
CPF_V4  = "98765432100"   # 987.654.321-00
CPF_V5  = "55566677720"   # 555.666.777-20
CPF_V6  = "10020030088"   # 100.200.300-88
CPF_V7  = "11122233396"   # 111.222.333-96
CPF_V8  = "44455566619"   # 444.555.666-19
CPF_V9  = "77788899941"   # 777.888.999-41
CPF_V10 = "22233344405"   # 222.333.444-05
CPF_V11 = "55577788889"   # 555.777.888-89
CPF_V12 = "33445566062"   # 334.455.660-62

# ── Helpers ───────────────────────────────────────────────────────────────────

def _criar_apolice() -> str:
    nr = f"2026.MOV.{uuid.uuid4().hex[:8].upper()}"
    r = client.post("/api/emissao/propostas", json={
        "nr_proposta": nr, "cd_empresa": 1,
        "cd_cpf_segurado": CPF_V12, "cd_produto": "VGC",
        "tp_capital": "F", "vl_capital": 100000.0, "dt_proposta": "20260101",
    })
    assert r.status_code == 201, r.text
    r2 = client.post(f"/api/emissao/propostas/{nr}/aceitar", json={
        "nr_proposta": nr, "tp_aceite": "MA", "id_usuario": "USR001",
    })
    assert r2.status_code == 200, r2.text
    return r2.json()["nr_apolice_gerada"]


def _csv_bytes(linhas: list[list]) -> bytes:
    """Monta CSV com cabeçalho padrão + linhas fornecidas."""
    header = [
        "subestipulante", "modulo", "nome_segurado", "cpf",
        "dt_nascimento", "dt_inclusao", "cargo", "tp_movimentacao",
        "vl_capital", "vl_salario", "nr_fator_mult", "cd_motivo", "ds_observacao",
    ]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    for linha in linhas:
        w.writerow(linha)
    return buf.getvalue().encode("utf-8-sig")


def _upload_csv(nr_apolice: str, linhas: list[list],
                dry_run: bool = False, competencia: str = "202606") -> dict:
    content = _csv_bytes(linhas)
    r = client.post(
        f"/api/emissao/apolices/{nr_apolice}/movimentacao/importar"
        f"?id_usuario=USR001&cd_competencia={competencia}&dry_run={str(dry_run).lower()}",
        files={"arquivo": ("movimentacao.csv", content, "text/csv")},
    )
    return r


# ══════════════════════════════════════════════════════════════════════════════
# UNITÁRIOS — serviço movimentacao_segurados
# ══════════════════════════════════════════════════════════════════════════════

class TestServicoParsers:

    def test_normalizar_col(self):
        assert _normalizar_col("Módulo") == "modulo"
        assert _normalizar_col("  Nome Segurado  ") == "nome_segurado"
        assert _normalizar_col("DT_NASCIMENTO") == "dt_nascimento"

    def test_limpar_cpf_valido(self):
        assert _limpar_cpf("123.456.789-01") == "12345678901"
        assert _limpar_cpf("12345678901") == "12345678901"

    def test_limpar_cpf_invalido(self):
        with pytest.raises(ValueError, match="CPF inválido"):
            _limpar_cpf("1234")

    def test_parsear_data_ddmmaaaa(self):
        assert _parsear_data("15/03/1985") == "19850315"

    def test_parsear_data_aaaammdd(self):
        assert _parsear_data("20260601") == "20260601"

    def test_parsear_data_iso(self):
        assert _parsear_data("2026-06-01") == "20260601"

    def test_parsear_data_objeto_date(self):
        from datetime import date
        assert _parsear_data(date(2026, 6, 1)) == "20260601"

    def test_parsear_data_vazia(self):
        assert _parsear_data(None) == ""
        assert _parsear_data("") == ""

    def test_parsear_data_invalida(self):
        with pytest.raises(ValueError):
            _parsear_data("janeiro de 2026")

    def test_parsear_valor_br(self):
        assert _parsear_valor("200.000,00") == pytest.approx(200000.0)

    def test_parsear_valor_inteiro(self):
        assert _parsear_valor(200000) == pytest.approx(200000.0)

    def test_parsear_valor_float(self):
        assert _parsear_valor(200000.50) == pytest.approx(200000.50)

    def test_parsear_valor_zero_retorna_none(self):
        assert _parsear_valor(0) is None
        assert _parsear_valor("0") is None

    def test_parsear_valor_vazio(self):
        assert _parsear_valor(None) is None
        assert _parsear_valor("") is None

    def test_tp_movimentacao_aliases(self):
        assert _tp_movimentacao("INC") == "INC"
        assert _tp_movimentacao("Inclusão") == "INC"
        assert _tp_movimentacao("ADMISSAO") == "INC"
        assert _tp_movimentacao("demissão") == "EXC"
        assert _tp_movimentacao("SAIDA") == "EXC"
        assert _tp_movimentacao("CAPITAL") == "CAP"
        assert _tp_movimentacao("SUSPENSÃO") == "SUS"
        assert _tp_movimentacao("Reativação") == "REA"
        assert _tp_movimentacao(None) == "INC"
        assert _tp_movimentacao("XPTO") == "INC"  # desconhecido → INC

    def test_mapear_colunas_aliases(self):
        cabecalho = ["Nome", "CPF", "Admissao", "Cargo", "Capital"]
        mapa = _mapear_colunas(cabecalho)
        assert "nome_segurado" in mapa
        assert "cpf" in mapa
        assert "dt_inclusao" in mapa
        assert "cargo" in mapa
        assert "vl_capital" in mapa

    def test_mapear_colunas_pt_acento(self):
        cabecalho = ["Módulo", "Data de Inclusão", "Funcionário"]
        mapa = _mapear_colunas(cabecalho)
        assert "modulo" in mapa
        assert "dt_inclusao" in mapa

    def test_processar_csv_basico(self):
        from datetime import date
        nr_apolice = "APO.UNIT.001"
        today = date.today().strftime("%d/%m/%Y")
        content = _csv_bytes([
            ["Sub1", "VG", "JOAO SILVA", CPF_V1,
             "15/03/1985", today, "Funcionario", "INC",
             200000, None, None, "ADMS", ""],
        ])
        result = processar_movimentacao("teste.csv", content, nr_apolice, "USR001")
        assert result.total_linhas == 1
        assert result.total_sucesso == 1
        assert result.total_erros == 0
        assert result.endossos[0]["cd_cpf_segurado"] == CPF_V1
        assert result.endossos[0]["nm_segurado"] == "JOAO SILVA"
        assert result.endossos[0]["tp_endosso"] == "INC"

    def test_processar_csv_cpf_invalido(self):
        nr_apolice = "APO.UNIT.002"
        content = _csv_bytes([
            ["Sub1", "VG", "JOAO SILVA", "INVALIDO",
             "15/03/1985", "15/09/2026", "Funcionario", "INC", 200000, "", "", "", ""],
        ])
        result = processar_movimentacao("teste.csv", content, nr_apolice, "USR001")
        assert result.total_erros == 1
        assert "CPF inválido" in result.erros[0]["erro"]

    def test_processar_csv_data_invalida(self):
        content = _csv_bytes([
            ["Sub1", "VG", "JOAO SILVA", CPF_V2,
             "15/03/1985", "INVALIDA", "Funcionario", "INC", 200000, "", "", "", ""],
        ])
        result = processar_movimentacao("teste.csv", content, "APO.UNIT.003", "USR001")
        assert result.total_erros == 1

    def test_processar_csv_nome_vazio(self):
        from datetime import date
        today = date.today().strftime("%d/%m/%Y")
        content = _csv_bytes([
            ["Sub1", "VG", "", CPF_V3,
             "15/03/1985", today, "Funcionario", "INC", 200000, "", "", "", ""],
        ])
        result = processar_movimentacao("teste.csv", content, "APO.UNIT.004", "USR001")
        assert result.total_erros == 1

    def test_processar_csv_fator_por_cargo(self):
        from datetime import date
        today = date.today().strftime("%d/%m/%Y")
        content = _csv_bytes([
            ["Sub1", "VG", "GERENTE SILVA", CPF_V4,
             "", today, "Gerencial", "INC", "", 5000, "", "", ""],
        ])
        result = processar_movimentacao("teste.csv", content, "APO.UNIT.005", "USR001")
        assert result.total_sucesso == 1
        # Gerencial → fator_mult = 5.0
        assert result.endossos[0]["nr_fator_mult"] == pytest.approx(5.0)

    def test_processar_sem_coluna_obrigatoria(self):
        content = b"sub;cargo\nSub1;Funcionario\n"
        with pytest.raises(ValueError, match="Colunas obrigatórias"):
            processar_movimentacao("teste.csv", content, "APO.UNIT.006", "USR001")

    def test_sumario_por_subestipulante(self):
        from datetime import date
        today = date.today().strftime("%d/%m/%Y")
        content = _csv_bytes([
            ["Sub1", "VG", "SEG A", CPF_V5, "", today, "F", "INC", 100000, "", "", "", ""],
            ["Sub1", "VG", "SEG B", CPF_V6, "", today, "F", "INC", 100000, "", "", "", ""],
            ["Sub2", "AP", "SEG C", CPF_V7, "", today, "G", "INC", 200000, "", "", "", ""],
        ])
        result = processar_movimentacao("teste.csv", content, "APO.UNIT.007", "USR001")
        assert result.sumario_sub.get("Sub1") == 2
        assert result.sumario_sub.get("Sub2") == 1


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO — endpoints FastAPI
# ══════════════════════════════════════════════════════════════════════════════

class TestTemplateEndpoints:
    def test_download_template_csv(self):
        r = client.get("/api/emissao/movimentacao/template")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        text = r.content.decode("utf-8-sig")
        assert "nome_segurado" in text
        assert "cpf" in text
        assert "dt_inclusao" in text

    def test_download_template_xlsx(self):
        r = client.get("/api/emissao/movimentacao/template.xlsx")
        assert r.status_code in (200, 503)  # 503 se openpyxl não instalado
        if r.status_code == 200:
            assert "spreadsheetml" in r.headers["content-type"]
            assert len(r.content) > 1000  # arquivo real, não vazio


class TestImportacaoIntegracao:

    def test_dry_run_valida_sem_gravar(self):
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        r = _upload_csv(nr_apolice, [
            ["Sub1", "VG", "JOAO SILVA", CPF_V1,
             "15/03/1985", today, "Funcionario", "INC",
             200000, "", "", "ADMS", ""],
        ], dry_run=True)
        assert r.status_code == 200
        data = r.json()
        assert data["dry_run"] is True
        assert data["total_sucesso"] == 1
        assert data["sucesso"][0]["status"] == "DRY_RUN"
        assert data["sucesso"][0]["nr_endosso"] is None
        # Não deve ter criado cobertura
        r2 = client.get(f"/api/emissao/apolices/{nr_apolice}/coberturas")
        assert len(r2.json()) == 0

    def test_importar_um_segurado(self):
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        r = _upload_csv(nr_apolice, [
            ["Sub1", "Vida em Grupo", "MARIA SOUZA", CPF_V4,
             "22/07/1990", today, "Gerencial", "INC",
             350000, "", "", "ADMS", "Gerente regional"],
        ])
        assert r.status_code == 200
        data = r.json()
        assert data["total_sucesso"] == 1
        assert data["total_erros"] == 0
        assert data["sucesso"][0]["nome"] == "MARIA SOUZA"
        assert data["sucesso"][0]["nr_endosso"] is not None
        assert data["sucesso"][0]["status"] == "OK"
        # Cobertura criada
        r2 = client.get(f"/api/emissao/apolices/{nr_apolice}/coberturas")
        assert len(r2.json()) == 1
        assert r2.json()[0]["cd_cpf_segurado"] == CPF_V4

    def test_importar_multiplos_segurados_por_sub(self):
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        linhas = [
            ["Sub1", "VG", "SEG ALPHA", CPF_V5, "10/05/1985", today, "Funcionario", "INC", 100000, "", "",    "", ""],
            ["Sub1", "VG", "SEG BETA",  CPF_V6, "22/08/1990", today, "Gerencial",   "INC", 300000, "", "",    "", ""],
            ["Sub2", "AP", "SEG GAMMA", CPF_V7, "03/11/1978", today, "Diretoria",   "INC", "",     8000, 6.0, "", "Capital múltiplo"],
            ["Sub2", "AP", "SEG DELTA", CPF_V8, "17/03/1995", today, "Funcionario", "INC", 150000, "", "",    "", ""],
        ]
        r = _upload_csv(nr_apolice, linhas)
        assert r.status_code == 200
        data = r.json()
        assert data["total_sucesso"] == 4
        assert data["sumario_sub"]["Sub1"] == 2
        assert data["sumario_sub"]["Sub2"] == 2

    def test_importar_exclusao(self):
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        # Primeiro inclui
        _upload_csv(nr_apolice, [
            ["Sub1", "VG", "ANA LIMA", CPF_V9, "14/06/1988", today, "F", "INC", 100000, "", "", "", ""],
        ])
        # Depois exclui
        r = _upload_csv(nr_apolice, [
            ["Sub1", "VG", "ANA LIMA", CPF_V9, "14/06/1988", today, "F", "EXC", "", "", "", "DEMI", "Demissão"],
        ])
        assert r.status_code == 200
        # Cobertura deve estar CANCELADA
        r2 = client.get(f"/api/emissao/apolices/{nr_apolice}/coberturas/{CPF_V9}")
        assert r2.json()["cd_status_cobertura"] == "CL"

    def test_importar_com_cpf_invalido_erro_linha(self):
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        linhas = [
            ["Sub1", "VG", "VALIDO",   CPF_V10,      "25/09/1982", today, "F", "INC", 100000, "", "", "", ""],
            ["Sub1", "VG", "INVALIDO", "CPF_ERRADO",  "25/09/1982", today, "F", "INC", 100000, "", "", "", ""],
        ]
        r = _upload_csv(nr_apolice, linhas)
        assert r.status_code == 200
        data = r.json()
        assert data["total_sucesso"] == 1
        assert data["total_erros"] == 1
        assert "CPF" in data["erros"][0]["erro"]

    def test_importar_apolice_inexistente(self):
        content = _csv_bytes([
            ["Sub1", "VG", "JOAO", "12345678901", "", "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        r = client.post(
            "/api/emissao/apolices/NAOEXISTE/movimentacao/importar?id_usuario=USR001",
            files={"arquivo": ("mov.csv", content, "text/csv")},
        )
        assert r.status_code == 404

    def test_importar_formato_invalido(self):
        nr_apolice = _criar_apolice()
        r = client.post(
            f"/api/emissao/apolices/{nr_apolice}/movimentacao/importar?id_usuario=USR001",
            files={"arquivo": ("planilha.txt", b"dados", "text/plain")},
        )
        assert r.status_code == 422

    def test_importar_e_faturar(self):
        """Fluxo completo: importar planilha → gerar fatura do mês."""
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        # Importa 3 segurados
        linhas = [
            ["Sub1", "VG", "SEG 001", CPF_V5, "01/01/1980", today, "Gerencial",   "INC", 300000, "", "", "ADMS", ""],
            ["Sub1", "VG", "SEG 002", CPF_V6, "15/05/1990", today, "Funcionario", "INC", 100000, "", "", "ADMS", ""],
            ["Sub2", "AP", "SEG 003", CPF_V7, "20/11/1975", today, "Diretoria",   "INC", 500000, "", "", "ADMS", ""],
        ]
        r_imp = _upload_csv(nr_apolice, linhas)
        assert r_imp.status_code == 200
        assert r_imp.json()["total_sucesso"] == 3

        # Gera fatura da competência 202606
        r_fat = client.post(f"/api/emissao/apolices/{nr_apolice}/faturamento", json={
            "nr_apolice":     nr_apolice,
            "cd_competencia": "202606",
            "dt_vencimento":  "20260610",
            "forma_cobranca": "BO",
            "id_usuario":     "USR001",
        })
        assert r_fat.status_code == 201
        fat = r_fat.json()
        assert fat["nr_segurados"] == 3
        assert fat["vl_total_bruto"] > 0
        # Cada item deve ter IPCA aplicado
        for item in fat["itens"]:
            assert item["vl_capital_coberto"] > 0
            assert item["vl_premio_bruto"] > 0

    def test_importar_alias_portugues(self):
        """Planilha com colunas em português com acento deve ser reconhecida."""
        from datetime import date
        nr_apolice = _criar_apolice()
        today = date.today().strftime("%d/%m/%Y")
        linhas_header = [
            "Subestipulante", "Módulo", "Funcionário", "CPF",
            "Data de Nascimento", "Admissão", "Cargo",
            "Movimentação", "Capital", "Salário", "Fator", "Motivo", "Observação"
        ]
        linha_dado = [
            "Sub1", "VG", "CARLOS MENDES", CPF_V11,
            "10/10/1990", today, "Gerencial",
            "INC", 250000, "", "", "ADMS", ""
        ]
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(linhas_header)
        w.writerow(linha_dado)
        content = buf.getvalue().encode("utf-8-sig")

        r = client.post(
            f"/api/emissao/apolices/{nr_apolice}/movimentacao/importar?id_usuario=USR001",
            files={"arquivo": ("mov.csv", content, "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_sucesso"] == 1
        assert data["sucesso"][0]["nome"] == "CARLOS MENDES"
        assert data["sucesso"][0]["subestipulante"] == "Sub1"
