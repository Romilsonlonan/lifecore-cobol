"""
Testes — Motor de Críticas de Segurados
Cobertura:
  - Unitários: algoritmo CPF, faixas de idade, datas, nomes
  - Integração: endpoints /criticas/catalogo, /criticas/parametros-idade
  - Integração: /criticas/cpf/validar
  - Integração: importação com críticas bloqueantes, manuais e alertas
  - Integração: liberação e bloqueio manual (W025)
"""
import io
import csv
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.criticas_segurado import (
    _validar_cpf_algoritmo,
    _calcular_idade,
    _validar_idade,
    _validar_dt_inclusao,
    _validar_nome,
    executar_criticas,
    SeveridadeCritica,
)

client = TestClient(app)

# CPFs válidos gerados pelo algoritmo (para testes)
CPF_VALIDO_1 = "11144477735"  # CPF válido real
CPF_VALIDO_2 = "52998224725"  # CPF válido real
CPF_INVALIDO = "11111111111"  # todos iguais → inválido
CPF_DIGITO_ERRADO = "12345678901"  # dígito verificador incorreto


# ── Helper ────────────────────────────────────────────────────────────────────

def _criar_apolice() -> str:
    nr = f"2026.CRIT.{uuid.uuid4().hex[:8].upper()}"
    r = client.post("/api/emissao/propostas", json={
        "nr_proposta": nr, "cd_empresa": 1,
        "cd_cpf_segurado": CPF_VALIDO_1,
        "cd_produto": "VGC", "tp_capital": "F",
        "vl_capital": 100000.0, "dt_proposta": "20260101",
    })
    assert r.status_code == 201, r.text
    r2 = client.post(f"/api/emissao/propostas/{nr}/aceitar", json={
        "nr_proposta": nr, "tp_aceite": "MA", "id_usuario": "USR001",
    })
    assert r2.status_code == 200, r2.text
    return r2.json()["nr_apolice_gerada"]


def _csv_bytes(linhas: list[list]) -> bytes:
    header = [
        "subestipulante", "modulo", "nome_segurado", "cpf",
        "dt_nascimento", "dt_inclusao", "cargo", "tp_movimentacao",
        "vl_capital", "vl_salario", "nr_fator_mult", "cd_motivo", "ds_observacao",
    ]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    for l in linhas:
        w.writerow(l)
    return buf.getvalue().encode("utf-8-sig")


def _importar(nr_apolice: str, linhas: list[list], dry_run=False) -> dict:
    content = _csv_bytes(linhas)
    r = client.post(
        f"/api/emissao/apolices/{nr_apolice}/movimentacao/importar"
        f"?id_usuario=USR001&cd_competencia=202606&dry_run={str(dry_run).lower()}"
        f"&verificar_receita=false",
        files={"arquivo": ("mov.csv", content, "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════════════
# UNITÁRIOS — algoritmo CPF
# ══════════════════════════════════════════════════════════════════════════════

class TestValidacaoCPF:

    def test_cpf_valido_1(self):
        assert _validar_cpf_algoritmo(CPF_VALIDO_1) is True

    def test_cpf_valido_2(self):
        assert _validar_cpf_algoritmo(CPF_VALIDO_2) is True

    def test_cpf_todos_iguais(self):
        assert _validar_cpf_algoritmo(CPF_INVALIDO) is False

    def test_cpf_digito_errado(self):
        # 12345678901 — dígitos verificadores incorretos
        assert _validar_cpf_algoritmo("12345678901") is False

    def test_cpf_tamanho_errado(self):
        assert _validar_cpf_algoritmo("1234") is False

    def test_critica_e001_gerada(self):
        """CPF com estrutura de 11 dígitos mas dígito verificador errado → E001."""
        r = executar_criticas(
            cpf="12345678901", nome="FULANO", dt_nascimento="19850101",
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E001" in codigos

    def test_critica_e002_todos_iguais(self):
        r = executar_criticas(
            cpf=CPF_INVALIDO, nome="FULANO", dt_nascimento="19850101",
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E002" in codigos

    def test_cpf_valido_sem_criticas_bloqueantes(self):
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="JOAO SILVA", dt_nascimento="19850315",
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        assert not r.tem_bloqueante


# ══════════════════════════════════════════════════════════════════════════════
# UNITÁRIOS — faixas de idade
# ══════════════════════════════════════════════════════════════════════════════

class TestValidacaoIdade:

    def test_calcular_idade_normal(self):
        assert _calcular_idade("19850315", "20260601") == 41

    def test_calcular_idade_aniversario_no_dia(self):
        assert _calcular_idade("19860601", "20260601") == 40

    def test_calcular_idade_antes_aniversario(self):
        assert _calcular_idade("19860602", "20260601") == 39

    def test_critica_e012_menor_de_14(self):
        """Criança de 10 anos → E012 (bloqueante)."""
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 10)
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="CRIANCA SILVA",
            dt_nascimento=nasc.strftime("%Y%m%d"),
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E012" in codigos
        assert r.tem_bloqueante

    def test_critica_e013_entre_65_e_70(self):
        """68 anos → E013 (bloqueante — acima do máximo operacional)."""
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 68)
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="IDOSO SILVA",
            dt_nascimento=nasc.strftime("%Y%m%d"),
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E013" in codigos
        assert r.tem_bloqueante

    def test_critica_w025_acima_70_novo_segurado(self):
        """72 anos, novo segurado (INC) → W025 (MANU — pende liberação)."""
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 72)
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="MUITO IDOSO",
            dt_nascimento=nasc.strftime("%Y%m%d"),
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "W025" in codigos
        assert r.tem_manual_pendente
        assert not r.tem_bloqueante  # MANU, não BLOQ

    def test_critica_w025_acima_70_segurado_existente(self):
        """72 anos, segurado JÁ EXISTENTE → W025 downgrade para ALRT."""
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 72)
        coberturas_mock = {"APO.TEST:11144477735": {"cd_status_cobertura": "AT"}}
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="MUITO IDOSO",
            dt_nascimento=nasc.strftime("%Y%m%d"),
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas=coberturas_mock, verificar_receita=False,
        )
        # Para segurado existente, W025 vira ALRT
        w025 = next((c for c in r.criticas if c.codigo == "W025"), None)
        assert w025 is not None
        assert w025.severidade == SeveridadeCritica.ALRT

    def test_critica_w026_faixa_atencao(self):
        """62 anos → W026 (alerta — faixa de atenção)."""
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 62)
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="SENIOR SILVA",
            dt_nascimento=nasc.strftime("%Y%m%d"),
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "W026" in codigos
        assert not r.tem_bloqueante

    def test_sem_critica_idade_normal(self):
        """35 anos → nenhuma crítica de idade."""
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="ADULTO SILVA",
            dt_nascimento="19910315",
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E012" not in codigos
        assert "E013" not in codigos
        assert "W025" not in codigos

    def test_critica_e010_sem_data_nascimento_inc(self):
        """Inclusão sem data de nascimento → E010."""
        r = executar_criticas(
            cpf=CPF_VALIDO_1, nome="FULANO SILVA",
            dt_nascimento=None,
            dt_inclusao="20260601", tp_movimentacao="INC",
            nr_apolice="APO.TEST", coberturas={}, verificar_receita=False,
        )
        codigos = [c.codigo for c in r.criticas]
        assert "E010" in codigos
        assert r.tem_bloqueante


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO — endpoints de catálogo e validação de CPF
# ══════════════════════════════════════════════════════════════════════════════

class TestCatalogoCriticas:

    def test_catalogo_retorna_todos_codigos(self):
        r = client.get("/api/emissao/criticas/catalogo")
        assert r.status_code == 200
        dados = r.json()
        codigos = [c["codigo"] for c in dados]
        for esperado in ["E001", "E002", "E010", "E012", "W025", "E013", "W026"]:
            assert esperado in codigos

    def test_parametros_idade(self):
        r = client.get("/api/emissao/criticas/parametros-idade")
        assert r.status_code == 200
        d = r.json()
        assert d["idade_minima"] == 14
        assert d["idade_maxima_operat"] == 65
        assert d["idade_implementacao"] == 70

    def test_validar_cpf_invalido_formato(self):
        r = client.post("/api/emissao/criticas/cpf/validar", json={
            "cpf": "1234", "verificar_receita": False,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["fl_valido"] is False
        assert any(c["codigo"] == "E002" for c in d["criticas"])

    def test_validar_cpf_digito_errado(self):
        r = client.post("/api/emissao/criticas/cpf/validar", json={
            "cpf": "12345678901", "verificar_receita": False,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["fl_valido"] is False
        assert any(c["codigo"] == "E001" for c in d["criticas"])

    def test_validar_cpf_valido_sem_receita(self):
        r = client.post("/api/emissao/criticas/cpf/validar", json={
            "cpf": CPF_VALIDO_1, "verificar_receita": False,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["fl_valido"] is True
        assert d["cpf_formatado"] is not None

    def test_validar_cpf_com_mascara(self):
        cpf_mascarado = f"{CPF_VALIDO_1[:3]}.{CPF_VALIDO_1[3:6]}.{CPF_VALIDO_1[6:9]}-{CPF_VALIDO_1[9:]}"
        r = client.post("/api/emissao/criticas/cpf/validar", json={
            "cpf": cpf_mascarado, "verificar_receita": False,
        })
        assert r.status_code == 200
        assert r.json()["fl_valido"] is True


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO — importação com críticas
# ══════════════════════════════════════════════════════════════════════════════

class TestImportacaoComCriticas:

    def test_cpf_invalido_bloqueado_na_importacao(self):
        nr = _criar_apolice()
        data = _importar(nr, [
            ["Sub1", "VG", "JOAO SILVA", "12345678901",
             "15/03/1985", "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        # CPF com dígito errado → E001 → bloqueante → vai para erros
        assert data["total_erros"] >= 1
        erros = data["erros"]
        assert any("E001" in e["erro"] for e in erros)

    def test_cpf_todos_iguais_bloqueado(self):
        nr = _criar_apolice()
        data = _importar(nr, [
            ["Sub1", "VG", "JOAO SILVA", CPF_INVALIDO,
             "15/03/1985", "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        assert data["total_erros"] >= 1
        assert any("E002" in e["erro"] for e in data["erros"])

    def test_menor_de_idade_bloqueado(self):
        nr = _criar_apolice()
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 10)
        data = _importar(nr, [
            ["Sub1", "VG", "CRIANCA SILVA", CPF_VALIDO_1,
             nasc.strftime("%d/%m/%Y"), "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        assert data["total_erros"] >= 1
        assert any("E012" in e["erro"] for e in data["erros"])

    def test_w025_pende_liberacao_manual(self):
        """Segurado > 70 anos na inclusão → status CRITICA_MANU, não processado."""
        nr = _criar_apolice()
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 72)
        data = _importar(nr, [
            ["Sub1", "VG", "MUITO IDOSO", CPF_VALIDO_1,
             nasc.strftime("%d/%m/%Y"), "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        assert data["total_pendente_manu"] >= 1
        pendentes = [s for s in data["sucesso"] if s["status"] == "CRITICA_MANU"]
        assert len(pendentes) == 1
        # id_critica deve estar preenchido na crítica W025 (MANU)
        w025 = next((c for c in pendentes[0]["criticas"] if c["codigo"] == "W025"), None)
        assert w025 is not None, f"W025 não encontrado: {pendentes[0]['criticas']}"
        assert w025["id_critica"] is not None

    def test_w026_alerta_processa_normalmente(self):
        """Segurado de 62 anos → W026 (alerta), endosso gerado normalmente."""
        nr = _criar_apolice()
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 62)
        data = _importar(nr, [
            ["Sub1", "VG", "SENIOR SILVA", CPF_VALIDO_1,
             nasc.strftime("%d/%m/%Y"), "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        ok = [s for s in data["sucesso"] if s["status"] in ("OK", "AVISO")]
        assert len(ok) == 1
        assert any(c["codigo"] == "W026" for c in ok[0]["criticas"])
        assert ok[0]["nr_endosso"] is not None

    def test_sem_data_nascimento_bloqueado_para_inc(self):
        """Inclusão sem dt_nascimento → E010 bloqueante."""
        nr = _criar_apolice()
        data = _importar(nr, [
            ["Sub1", "VG", "FULANO SILVA", CPF_VALIDO_1,
             "", "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        assert data["total_erros"] >= 1
        assert any("E010" in e["erro"] for e in data["erros"])

    def test_cpf_valido_sem_criticas_processado(self):
        """CPF válido, adulto, dados corretos → OK ou AVISO sem críticas bloqueantes."""
        from datetime import date
        nr = _criar_apolice()
        hoje = date.today().strftime("%d/%m/%Y")
        # Usa CPF_VALIDO_2 para evitar colisão com outros testes que usam CPF_VALIDO_1
        data = _importar(nr, [
            ["Sub1", "VG", "JOAO ADULTO", CPF_VALIDO_2,
             "15/03/1985", hoje, "F", "INC", 100000, "", "", "", ""],
        ])
        # Não deve haver bloqueantes; status pode ser OK ou AVISO (W042 se data retroativa)
        processados = [s for s in data["sucesso"] if s["status"] in ("OK", "AVISO")]
        assert len(processados) == 1, f"Esperado processado, dados: {data['sucesso']}"
        assert processados[0]["nr_endosso"] is not None
        assert data["total_erros"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO — liberação e bloqueio de W025
# ══════════════════════════════════════════════════════════════════════════════

class TestLiberacaoManual:

    def _importar_com_w025(self) -> tuple[str, str]:
        """Importa um segurado > 70 anos e retorna (nr_apolice, id_critica)."""
        nr = _criar_apolice()
        from datetime import date
        nasc = date.today().replace(year=date.today().year - 72)
        data = _importar(nr, [
            ["Sub1", "VG", "MUITO IDOSO", CPF_VALIDO_1,
             nasc.strftime("%d/%m/%Y"), "01/06/2026", "F", "INC", 100000, "", "", "", ""],
        ])
        pendentes = [s for s in data["sucesso"] if s["status"] == "CRITICA_MANU"]
        assert len(pendentes) == 1, f"Esperado 1 pendente, encontrado: {data}"
        # Pega especificamente o id_critica da W025 (MANU)
        w025 = next((c for c in pendentes[0]["criticas"] if c["codigo"] == "W025"), None)
        assert w025 is not None, f"W025 não encontrado em: {pendentes[0]['criticas']}"
        assert w025["id_critica"] is not None, "id_critica deve estar preenchido para W025 MANU"
        id_crit = w025["id_critica"]
        return nr, id_crit

    def test_listar_criticas_pendentes(self):
        nr, _ = self._importar_com_w025()
        r = client.get(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas?status_liberacao=PENDENTE"
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1
        assert r.json()[0]["codigo"] == "W025"

    def test_liberar_critica(self):
        nr, id_crit = self._importar_com_w025()
        r = client.post(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas/{id_crit}/liberar",
            json={"id_usuario": "ANALISTA01", "ds_justificativa": "Segurado autorizado pela diretoria."},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["decisao"] == "LIBERADO"
        assert d["id_usuario"] == "ANALISTA01"
        # Status deve mudar para LIBERADO
        r2 = client.get(f"/api/emissao/apolices/{nr}/movimentacao/criticas")
        crit = next(c for c in r2.json() if c["id_critica"] == id_crit)
        assert crit["status_liberacao"] == "LIBERADO"

    def test_bloquear_critica(self):
        nr, id_crit = self._importar_com_w025()
        r = client.post(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas/{id_crit}/bloquear",
            json={"id_usuario": "ANALISTA01", "ds_justificativa": "Segurado acima do limite sem autorização."},
        )
        assert r.status_code == 200
        assert r.json()["decisao"] == "BLOQUEADO"

    def test_liberar_duas_vezes_retorna_409(self):
        nr, id_crit = self._importar_com_w025()
        client.post(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas/{id_crit}/liberar",
            json={"id_usuario": "ANALISTA01", "ds_justificativa": "Autorizado."},
        )
        r2 = client.post(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas/{id_crit}/liberar",
            json={"id_usuario": "ANALISTA01", "ds_justificativa": "Dupla tentativa."},
        )
        assert r2.status_code == 409

    def test_critica_inexistente_retorna_404(self):
        nr = _criar_apolice()
        r = client.post(
            f"/api/emissao/apolices/{nr}/movimentacao/criticas/{uuid.uuid4()}/liberar",
            json={"id_usuario": "ANALISTA01", "ds_justificativa": "Teste."},
        )
        assert r.status_code == 404
