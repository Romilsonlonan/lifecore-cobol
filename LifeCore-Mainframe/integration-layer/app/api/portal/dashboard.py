"""
Portal — Dashboard com dados reais do Supabase
GET /api/portal/dashboard

Consolida KPIs, últimas transações (importações) e contagens reais.
Todas as queries são wrapped em try/except — falha parcial retorna zeros,
nunca um HTTP 500.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


def _sb():
    from app.services.supabase_client import get_client
    return get_client()


# ── Zero-value defaults ───────────────────────────────────────────────────────
_ZERO_KPIS = {
    "total_estipulantes":        0,
    "total_apolices_ativas":     0,
    "total_apolices_canceladas": 0,
    "total_segurados_ativos":    0,
    "total_segurados_excluidos": 0,
    "total_subestipulantes":     0,
    "subs_canceladas":           0,
    "faturamento_realizado":     0.0,
    "faturamento_pendente":      0.0,
}


@router.get("", summary="Dashboard — KPIs e últimas transações (Supabase)")
def dashboard() -> dict:
    errors: list[str] = []

    # ── 1. Estipulantes ───────────────────────────────────────────────────────
    estipulantes: list[dict] = []
    try:
        res = _sb().table("estipulantes").select(
            "nr_apolice, nm_razao_social, dt_cadastro, subestipulantes"
        ).execute()
        estipulantes = res.data or []
    except Exception as exc:
        errors.append(f"estipulantes: {exc}")
        logger.warning("dashboard – estipulantes query failed: %s", exc)

    total_estipulantes = len(estipulantes)

    # Subestipulantes (JSONB array, no cd_status — just count)
    total_subs = 0
    for est in estipulantes:
        subs = est.get("subestipulantes") or []
        if isinstance(subs, list):
            total_subs += len(subs)

    # ── 2. Coberturas (segurados) ─────────────────────────────────────────────
    coberturas: list[dict] = []
    try:
        res = _sb().table("coberturas").select(
            "cd_cpf, cd_status, nr_apolice, vl_capital"
        ).execute()
        coberturas = res.data or []
    except Exception as exc:
        errors.append(f"coberturas: {exc}")
        logger.warning("dashboard – coberturas query failed: %s", exc)

    cpfs_ativos   = {c["cd_cpf"] for c in coberturas if c.get("cd_status") == "AT"}
    cpfs_excluid  = {c["cd_cpf"] for c in coberturas if c.get("cd_status") == "EX"}
    apolices_ativas = {c["nr_apolice"] for c in coberturas if c.get("cd_status") == "AT"}
    apolices_canceladas = (
        {c["nr_apolice"] for c in coberturas if c.get("cd_status") == "EX"}
        - apolices_ativas
    )

    total_segurados_ativos  = len(cpfs_ativos)
    total_segurados_excluid = len(cpfs_excluid - cpfs_ativos)
    total_apolices_ativas   = len(apolices_ativas)
    total_apolices_cancelad = len(apolices_canceladas)

    # Faturamento: sum capital AT vs EX (reuse same query result)
    fat_realizado = sum(float(c.get("vl_capital") or 0) for c in coberturas if c.get("cd_status") == "AT")
    fat_pendente  = sum(float(c.get("vl_capital") or 0) for c in coberturas if c.get("cd_status") == "EX")

    # ── 3. Importações recentes ───────────────────────────────────────────────
    importacoes: list[dict] = []
    try:
        res = (
            _sb().table("importacao_vidas")
            .select(
                "id_importacao, nr_apolice, qt_registros, qt_validos, qt_erros, "
                "cd_status, dt_importacao, id_usuario, ts_inclusao"
            )
            .eq("dry_run", False)
            .order("ts_inclusao", desc=True)
            .limit(10)
            .execute()
        )
        importacoes = res.data or []
    except Exception as exc:
        errors.append(f"importacao_vidas: {exc}")
        logger.warning("dashboard – importacao_vidas query failed: %s", exc)

    nome_map = {e["nr_apolice"]: e.get("nm_razao_social", e["nr_apolice"]) for e in estipulantes}

    status_map = {"OK": "Concluído", "PE": "Pendente", "PA": "Parcial", "ERRO": "Erro"}

    ultimas_transacoes = []
    for imp in importacoes:
        nr   = imp.get("nr_apolice", "")
        stat = imp.get("cd_status", "PE")
        dt_raw = imp.get("dt_importacao", "")
        try:
            dt_fmt = datetime.strptime(dt_raw, "%Y%m%d").strftime("%d/%b/%Y")
        except Exception:
            dt_fmt = dt_raw

        ultimas_transacoes.append({
            "id":           (imp.get("id_importacao") or "")[:8].upper(),
            "nr_apolice":   nr,
            "nm_empresa":   nome_map.get(nr, nr),
            "dt":           dt_fmt,
            "ts":           imp.get("ts_inclusao", ""),
            "status":       status_map.get(stat, stat),
            "qt_registros": imp.get("qt_registros", 0),
            "qt_validos":   imp.get("qt_validos", 0),
            "qt_erros":     imp.get("qt_erros", 0),
            "id_usuario":   imp.get("id_usuario", "—"),
        })

    # ── 4. Atividades recentes ────────────────────────────────────────────────
    atividades = []
    for imp in importacoes[:7]:
        nr   = imp.get("nr_apolice", "")
        nome = nome_map.get(nr, nr)
        stat = imp.get("cd_status", "PE")
        qv   = imp.get("qt_validos", 0)
        qe   = imp.get("qt_erros", 0)
        ts_raw = imp.get("ts_inclusao", "")
        try:
            ts_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            hora  = ts_dt.astimezone(UTC).strftime("%H:%M")
        except Exception:
            hora = "—"

        if stat == "OK":
            descr = f"importou {qv} segurado{'s' if qv != 1 else ''} — apólice {nr}"
        elif stat == "PA":
            descr = f"importação parcial: {qv} ok, {qe} erro{'s' if qe != 1 else ''} — apólice {nr}"
        elif stat == "ERRO":
            descr = f"importação com erro — {qe} rejeitado{'s' if qe != 1 else ''} — apólice {nr}"
        else:
            descr = f"importação pendente — apólice {nr}"

        atividades.append({
            "actor":   imp.get("id_usuario", "SISTEMA"),
            "action":  descr,
            "empresa": nome,
            "hora":    hora,
            "status":  stat,
        })

    return {
        "kpis": {
            "total_estipulantes":        total_estipulantes,
            "total_apolices_ativas":     total_apolices_ativas,
            "total_apolices_canceladas": total_apolices_cancelad,
            "total_segurados_ativos":    total_segurados_ativos,
            "total_segurados_excluidos": total_segurados_excluid,
            "total_subestipulantes":     total_subs,
            "subs_canceladas":           0,          # no status field on subs
            "faturamento_realizado":     round(fat_realizado, 2),
            "faturamento_pendente":      round(fat_pendente, 2),
        },
        "ultimas_transacoes": ultimas_transacoes,
        "atividades": atividades,
        "errors": errors,           # debug: empty in production
        "gerado_em": datetime.now(UTC).isoformat(),
    }
