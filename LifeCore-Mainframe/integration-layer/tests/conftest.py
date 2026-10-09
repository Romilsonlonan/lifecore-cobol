"""
conftest.py — Fixtures globais para os testes de integração.

Responsabilidade: limpar dados residuais no Supabase antes de cada sessão
de testes, garantindo idempotência mesmo quando o banco real está conectado.
Os dados removidos são exclusivamente registros com chaves FIXAS usadas
pelas suítes de teste — nunca dados dinâmicos de outros testes.
"""
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _try_delete(table: str, col: str, val) -> None:
    """Apaga uma linha específica no Supabase silenciosamente (ignora erros)."""
    try:
        from app.repositories.supabase_repo import sb_available
        if not sb_available(table):
            return
        from app.services.supabase_client import get_client
        get_client().table(table).delete().eq(col, val).execute()
    except Exception:
        pass


def _supabase_cleanup() -> None:
    """
    Remove apenas os registros com CHAVES FIXAS usadas pelas suítes.
    Não remove dados dinâmicos (UUIDs) — apenas os literais hardcoded nos testes.
    """

    # ── propostas com nr_proposta fixo ────────────────────────────────────────
    # test_api.py usa '2026.PROP.TEST01'
    # test_config_apolice.py usa '2026.PROP.CFG001' — esse é criado pelo test,
    # mas precisa estar limpo para o primeiro POST retornar 201
    for nr in ("2026.PROP.TEST01", "2026.PROP.CFG001"):
        _try_delete("propostas", "nr_proposta", nr)

    # Limpa apolices geradas a partir dessas propostas fixas
    try:
        from app.repositories.supabase_repo import sb_available
        if sb_available("apolices"):
            from app.services.supabase_client import get_client
            sb = get_client()
            for nr_prop in ("2026.PROP.TEST01", "2026.PROP.CFG001"):
                res = sb.table("apolices").select("nr_apolice").eq(
                    "nr_proposta", nr_prop
                ).execute()
                for row in (res.data or []):
                    _try_delete("apolices", "nr_apolice", row["nr_apolice"])
    except Exception:
        pass

    # ── sinistros com nr_sinistro fixo ────────────────────────────────────────
    # test_api.py usa '2026.SIN.TEST01'
    _try_delete("sinistros", "nr_sinistro", "2026.SIN.TEST01")

    # ── taxas_ipca criadas pelos testes ───────────────────────────────────────
    # test_faturamento.py cria '202508' — seeds (202501-202507) ficam intactas
    _try_delete("taxas_ipca", "cd_competencia", "202508")
    _try_delete("taxas_ipca", "cd_competencia", "202509")
    # Garante que 202507 está vigente (pode ter sido desmarcada por run anterior)
    try:
        from app.repositories.supabase_repo import sb_available
        if sb_available("taxas_ipca"):
            from app.services.supabase_client import get_client
            sb = get_client()
            sb.table("taxas_ipca").update({"fl_vigente": False}).neq(
                "cd_competencia", "202507"
            ).execute()
            sb.table("taxas_ipca").update({"fl_vigente": True}).eq(
                "cd_competencia", "202507"
            ).execute()
    except Exception:
        pass

    # ── faturas criadas em test_faturamento ───────────────────────────────────
    try:
        from app.repositories.supabase_repo import sb_available
        if sb_available("faturas"):
            from app.services.supabase_client import get_client
            get_client().table("faturas").delete().like("nr_fatura", "FAT.2026.%").execute()
    except Exception:
        pass

    # ── corretoras criadas em test_corretagem ─────────────────────────────────
    # A seed '12345678000199' (Corretora Exemplo Ltda) NÃO é removida, mas
    # garante que os campos estejam corretos (pode ter sido inserida sem nm_cidade)
    try:
        from app.repositories.supabase_repo import sb_available
        if sb_available("corretoras"):
            from app.services.supabase_client import get_client
            get_client().table("corretoras").update({
                "nm_cidade": "São Paulo",
                "sg_estado": "SP",
                "nm_nome_reduzido": "CORRETORA EX",
                "cd_email": "contato@corretora.com.br",
                "nr_telefone": "1133445566",
                "nr_celular": "11987654321",
                "ds_site": "https://corretora.com.br",
                "nr_susep": "J1234",
            }).eq("cd_cnpj", "12345678000199").execute()
    except Exception:
        pass

    for cnpj in ("99887766000100", "77665544000100", "11112222000100"):
        _try_delete("corretoras", "cd_cnpj", cnpj)


# ── Fixture de sessão ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def cleanup_supabase_test_data():
    """Limpa dados residuais de runs anteriores no Supabase antes da sessão."""
    _supabase_cleanup()
    yield
