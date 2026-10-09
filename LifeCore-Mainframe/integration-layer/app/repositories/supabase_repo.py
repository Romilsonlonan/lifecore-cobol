"""
LifeCore — Supabase Repository Helper
======================================
Wrapper fino sobre o client Supabase que encapsula os padrões de
upsert, select e delete usados em todos os módulos migrados de in-memory.

Padrões:
  - _sb()           → singleton do client Supabase (lazy-init)
  - insert(table, row) → retorna a linha inserida
  - upsert(table, row, conflict_col) → upsert pelo campo chave
  - update(table, match, data) → UPDATE com filtro de igualdade
  - delete(table, match) → DELETE com filtro de igualdade
  - get_one(table, match) → primeira linha ou None
  - get_all(table, filters, order, limit) → lista de dicts

Erros do Supabase são propagados como RuntimeError com contexto.
Tabelas com migration pendente (PGRST205) retornam None/[] silenciosamente.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tabelas para as quais a migration já foi confirmada (cache em memória).
# Se uma query retornar PGRST205 (tabela não encontrada) a tabela é marcada
# como indisponível para toda a sessão e o caller cai no fallback in-memory.
_TABELAS_INDISPONIVEIS: set[str] = set()


def _sb():
    from app.services.supabase_client import get_client

    return get_client()


def sb_available(table: str | None = None) -> bool:
    """True se Supabase está conectado E (se table informada) a tabela não está na blacklist."""
    try:
        _sb()
    except Exception:
        return False
    if table and table in _TABELAS_INDISPONIVEIS:
        return False
    return True


def _is_table_missing(exc: Exception) -> bool:
    """True se o erro é PGRST205 — tabela não existe no Supabase ainda."""
    msg = str(exc)
    # postgrest.exceptions.APIError serializa como dict: {'code': 'PGRST205', ...}
    return (
        "PGRST205" in msg
        or "schema cache" in msg
        or "schema_cache" in msg
        or (hasattr(exc, "code") and getattr(exc, "code", "") == "PGRST205")
        or (
            isinstance(getattr(exc, "args", None), tuple)
            and any("PGRST205" in str(a) or "schema cache" in str(a) for a in exc.args)
        )
    )


def insert(table: str, row: dict[str, Any]) -> dict[str, Any]:
    if table in _TABELAS_INDISPONIVEIS:
        raise RuntimeError(f"Tabela '{table}' indisponível — migration pendente.")
    try:
        res = _sb().table(table).insert(row).execute()
        if not res.data:
            raise RuntimeError(f"Supabase insert em '{table}' não retornou dados.")
        return res.data[0]
    except RuntimeError:
        raise
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        raise


def upsert(table: str, row: dict[str, Any]) -> dict[str, Any]:
    if table in _TABELAS_INDISPONIVEIS:
        raise RuntimeError(f"Tabela '{table}' indisponível — migration pendente.")
    try:
        res = _sb().table(table).upsert(row).execute()
        if not res.data:
            raise RuntimeError(f"Supabase upsert em '{table}' não retornou dados.")
        return res.data[0]
    except RuntimeError:
        raise
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        raise


def update(table: str, match: dict[str, Any], data: dict[str, Any]) -> dict[str, Any] | None:
    if table in _TABELAS_INDISPONIVEIS:
        return None
    try:
        # postgrest-py: .update(data) retorna SyncFilterRequestBuilder que expõe .eq()
        q = _sb().table(table).update(data)
        for col, val in match.items():
            q = q.eq(col, val)
        res = q.execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        raise


def delete(table: str, match: dict[str, Any]) -> None:
    if table in _TABELAS_INDISPONIVEIS:
        return
    try:
        q = _sb().table(table)
        for col, val in match.items():
            q = q.eq(col, val)
        q.delete().execute()
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        raise


def get_one(table: str, match: dict[str, Any]) -> dict[str, Any] | None:
    if table in _TABELAS_INDISPONIVEIS:
        return None
    try:
        q = _sb().table(table).select("*")
        for col, val in match.items():
            q = q.eq(col, val)
        res = q.limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        return None


def get_all(
    table: str,
    filters: dict[str, Any] | None = None,
    order: str | None = None,
    desc: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if table in _TABELAS_INDISPONIVEIS:
        return []
    try:
        q = _sb().table(table).select("*")
        for col, val in (filters or {}).items():
            q = q.eq(col, val)
        if order:
            q = q.order(order, desc=desc)
        if limit:
            q = q.limit(limit)
        res = q.execute()
        return res.data or []
    except Exception as exc:
        if _is_table_missing(exc):
            _TABELAS_INDISPONIVEIS.add(table)
            logger.info("Tabela '%s' não encontrada — migration pendente. Usando fallback.", table)
        return []
