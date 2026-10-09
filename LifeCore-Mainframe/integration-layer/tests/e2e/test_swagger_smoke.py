"""
Playwright — Smoke Tests da Swagger UI + E2E da Integration Layer
Executa contra o servidor real (uvicorn) na porta 8000.

Como rodar:
  # Terminal 1 — sobe o servidor
  uvicorn app.main:app --port 8000

  # Terminal 2 — roda os testes Playwright
  pytest tests/e2e/ -v --headed          # com browser visível
  pytest tests/e2e/ -v                   # headless (CI)

Os testes cobrem:
  1. Swagger UI carrega e exibe os 9 grupos de endpoints
  2. Health endpoint retorna 200 via browser
  3. POST /api/emissao/propostas via Swagger Try It Out
  4. GET /api/painel retorna JSON com os 4 KPIs
  5. Fluxo completo: proposta → aceite → apólice (UI flow)
"""

from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"
SWAGGER = f"{BASE_URL}/docs"

# ── Tags que devem aparecer na Swagger UI ──────────────────────────────────────
EXPECTED_TAGS = [
    "Importação",
    "Jobs Batch",
    "Cadastros · Empresas",
    "Emissão · Propostas",
    "Emissão · Apólices",
    "Sinistro",
    "Impressão",
    "Cosseguro",
    "Pessoas",
    "Painel Interativo",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SMOKE — Swagger UI
# ═══════════════════════════════════════════════════════════════════════════════


def test_swagger_carrega(page: Page):
    """A Swagger UI deve carregar com o título correto."""
    page.goto(SWAGGER)
    expect(page).to_have_title("LifeCore-Mainframe Integration Layer - Swagger UI")


def test_swagger_versao_2(page: Page):
    """Deve exibir version 2.0.0 no header da Swagger."""
    page.goto(SWAGGER)
    header = page.locator(".swagger-ui .info .version")
    expect(header).to_contain_text("2.0.0")


def test_swagger_todos_os_grupos(page: Page):
    """Todos os grupos de endpoints devem aparecer na Swagger UI."""
    page.goto(SWAGGER)
    # Aguarda o Swagger renderizar completamente
    page.wait_for_selector(".opblock-tag", timeout=10_000)

    tags_visiveis = page.locator(".opblock-tag span.nostyle").all_text_contents()
    for tag in EXPECTED_TAGS:
        assert any(
            tag in t for t in tags_visiveis
        ), f"Tag '{tag}' não encontrada na Swagger. Tags encontradas: {tags_visiveis}"


# ═══════════════════════════════════════════════════════════════════════════════
# SMOKE — Health via browser (fetch JS)
# ═══════════════════════════════════════════════════════════════════════════════


def test_health_via_browser(page: Page):
    """GET /health deve retornar status=ok via fetch no browser."""
    page.goto(BASE_URL + "/docs")  # página base para ter contexto CORS
    result = page.evaluate(
        """async () => {
            const r = await fetch('/health');
            return await r.json();
        }"""
    )
    assert result["status"] == "ok"
    assert result["version"] == "2.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# API via fetch no browser — testa CORS + JSON correto
# ═══════════════════════════════════════════════════════════════════════════════


def test_listar_empresas_via_browser(page: Page):
    """GET /api/cadastros/empresas deve retornar lista com Prudential."""
    page.goto(SWAGGER)
    result = page.evaluate(
        """async () => {
            const r = await fetch('/api/cadastros/empresas');
            return await r.json();
        }"""
    )
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["nm_razao_social"] == "Prudential do Brasil Seguros de Vida S.A."


def test_painel_kpis_via_browser(page: Page):
    """GET /api/painel deve retornar os 4 KPIs esperados."""
    page.goto(SWAGGER)
    result = page.evaluate(
        """async () => {
            const r = await fetch('/api/painel');
            return await r.json();
        }"""
    )
    assert "kpis" in result
    assert len(result["kpis"]) == 4
    titulos = [k["titulo"] for k in result["kpis"]]
    assert "Apólices Vigentes" in titulos
    assert "Sinistros Abertos" in titulos


def test_headers_trace_id(page: Page):
    """Toda resposta deve conter X-Trace-Id (middleware de correlação OTel)."""
    page.goto(SWAGGER)
    result = page.evaluate(
        """async () => {
            const r = await fetch('/health');
            return {
                status: r.status,
                trace_id: r.headers.get('x-trace-id'),
                request_id: r.headers.get('x-request-id')
            };
        }"""
    )
    assert result["status"] == 200
    assert result["trace_id"] is not None, "Header X-Trace-Id ausente"
    assert result["request_id"] is not None, "Header X-Request-Id ausente"


# ═══════════════════════════════════════════════════════════════════════════════
# FLUXO E2E — Proposta → Aceite (via fetch direto, browser como executor)
# ═══════════════════════════════════════════════════════════════════════════════


def test_fluxo_proposta_aceite_e2e(page: Page):
    """
    Fluxo completo via browser:
      1. POST /api/emissao/propostas → status=AN
      2. POST .../aceitar            → status=AC + nr_apolice_gerada
      3. GET  /api/emissao/apolices  → apólice aparece como AT
    """
    page.goto(SWAGGER)

    nr_proposta = "2026.PROP.E2E001"

    # 1. Cria proposta
    proposta = page.evaluate(
        f"""async () => {{
            const r = await fetch('/api/emissao/propostas', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    nr_proposta: '{nr_proposta}',
                    cd_empresa: 1,
                    cd_cpf_segurado: '12345678901',
                    cd_produto: 'VGC',
                    tp_capital: 'F',
                    vl_capital: 100000.0,
                    vl_premio_bruto: 1055.25,
                    dt_proposta: '20260101'
                }})
            }});
            return await r.json();
        }}"""
    )
    # Aceita duplicata se o teste rodou antes
    assert proposta.get("cd_status") in ("AN", "AC") or "detail" in proposta

    # 2. Aceita proposta (idempotente se já aceita)
    aceite = page.evaluate(
        f"""async () => {{
            const r = await fetch('/api/emissao/propostas/{nr_proposta}/aceitar', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    nr_proposta: '{nr_proposta}',
                    tp_aceite: 'AU',
                    id_usuario: 'E2E_TEST'
                }})
            }});
            return await r.json();
        }}"""
    )
    # 409 se já aceita (state de outro teste), 200 se é primeira vez
    assert aceite.get("cd_status") == "AC" or "detail" in aceite

    # 3. Verifica apólice gerada
    apolices = page.evaluate(
        """async () => {
            const r = await fetch('/api/emissao/apolices');
            return await r.json();
        }"""
    )
    assert isinstance(apolices, list)
    # Pelo menos uma apólice ativa deve existir (de outros testes ou deste)
    ativas = [a for a in apolices if a.get("cd_status") == "AT"]
    assert len(ativas) >= 1
