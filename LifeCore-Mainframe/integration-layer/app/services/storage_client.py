"""
Storage Client — S3-compatible com fallback para Supabase Storage nativo
=========================================================================
Estratégia de dois modos:

  MODO S3 (quando STORAGE_ACCESS_KEY e STORAGE_SECRET_KEY estão definidos):
      Usa boto3 apontando para o endpoint S3 do Supabase Storage.
      Compatível também com MinIO (dev local) ou AWS S3 real.

  MODO SUPABASE NATIVO (fallback — quando as keys S3 não estão configuradas):
      Usa o cliente supabase-py diretamente com o service_role key.
      Funciona com o bucket 'ecm-docs' criado no Supabase Dashboard.
      Não requer nenhuma configuração extra além do SUPABASE_SERVICE_KEY
      já presente no .env.

Como configurar o MODO S3 (opcional, melhora performance):
    Storage → S3 Connection → Access keys → "+ New access key"
    Preencha STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY no .env.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET = settings.storage_bucket


# ── Modo S3 (boto3) ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _s3():
    import boto3
    from botocore.client import Config
    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        config=Config(signature_version="s3v4"),
        region_name=settings.storage_region,
    )
    return client


def _upload_s3(storage_path: str, data: bytes, content_type: str) -> None:
    import io
    _s3().upload_fileobj(
        io.BytesIO(data), BUCKET, storage_path,
        ExtraArgs={"ContentType": content_type},
    )
    logger.info("Storage S3: upload OK — %s (%d bytes)", storage_path, len(data))


def _signed_url_s3(storage_path: str, expires_in: int) -> str:
    url: str = _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": storage_path},
        ExpiresIn=expires_in,
    )
    return url


def _delete_s3(storage_path: str) -> None:
    _s3().delete_object(Bucket=BUCKET, Key=storage_path)
    logger.info("Storage S3: delete OK — %s", storage_path)


# ── Modo Supabase nativo (fallback) ───────────────────────────────────────────

def _sb():
    from app.services.supabase_client import get_client
    return get_client()


def _upload_supabase(storage_path: str, data: bytes, content_type: str) -> None:
    _sb().storage.from_(BUCKET).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    logger.info("Storage Supabase nativo: upload OK — %s (%d bytes)", storage_path, len(data))


def _signed_url_supabase(storage_path: str, expires_in: int) -> str:
    result = _sb().storage.from_(BUCKET).create_signed_url(
        path=storage_path,
        expires_in=expires_in,
    )
    url: str = result.get("signedURL") or result.get("signedUrl") or ""
    if not url:
        raise ValueError("Supabase não retornou URL assinada.")
    return url


def _delete_supabase(storage_path: str) -> None:
    _sb().storage.from_(BUCKET).remove([storage_path])
    logger.info("Storage Supabase nativo: delete OK — %s", storage_path)


# ── API pública — seleciona o modo automaticamente ────────────────────────────

def upload(storage_path: str, data: bytes, content_type: str) -> None:
    """Upload de arquivo para o storage. Usa S3 se configurado, Supabase nativo caso contrário."""
    if settings.storage_configured:
        _upload_s3(storage_path, data, content_type)
    else:
        logger.info("STORAGE_ACCESS_KEY não configurado — usando Supabase Storage nativo.")
        _upload_supabase(storage_path, data, content_type)


def signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Gera URL pré-assinada para visualização/download."""
    if settings.storage_configured:
        return _signed_url_s3(storage_path, expires_in)
    else:
        return _signed_url_supabase(storage_path, expires_in)


def delete(storage_path: str) -> None:
    """Remove arquivo do storage."""
    if settings.storage_configured:
        _delete_s3(storage_path)
    else:
        _delete_supabase(storage_path)
