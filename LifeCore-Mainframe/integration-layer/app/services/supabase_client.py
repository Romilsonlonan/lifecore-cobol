"""
LifeCore — Supabase Client
Cliente singleton usando service_role (acesso total ao banco).
Usado exclusivamente pelo backend Python — nunca expor no frontend.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """Retorna o cliente Supabase (singleton). Lazy-init na primeira chamada."""
    global _client
    if _client is not None:
        return _client

    from app.core.config import settings

    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError(
            "Supabase não configurado. "
            "Defina SUPABASE_URL e SUPABASE_SERVICE_KEY no .env"
        )

    from supabase import Client, create_client

    _client = create_client(settings.supabase_url, settings.supabase_service_key)
    logger.info("Supabase conectado: %s", settings.supabase_url)
    return _client
