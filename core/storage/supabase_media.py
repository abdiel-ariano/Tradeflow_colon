"""Supabase Storage backend: S3 writes with native Supabase read URLs.

django-storages S3Boto3Storage signs URLs with the S3-compatible endpoint
using ``service_role`` as AWSAccessKeyId, which browsers reject. Uploads
stay on S3; ``url()`` uses Supabase public or signed object URLs instead.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

log = logging.getLogger('tradeflow.media')


def _bucket_name() -> str:
    """Resolve the configured Supabase/S3 media bucket name."""
    opts = settings.STORAGES.get('default', {}).get('OPTIONS', {})
    return str(opts.get('bucket_name') or getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'media'))


def _normalize_object_path(name: str) -> str:
    """Normalize storage object keys to forward-slash paths."""
    return (name or '').replace('\\', '/').lstrip('/')


def supabase_public_url(name: str) -> str:
    """Build a native Supabase public object URL for the media bucket."""
    path = _normalize_object_path(name)
    if not path:
        return ''
    base = (getattr(settings, 'SUPABASE_URL', '') or '').rstrip('/')
    if not base:
        return ''
    bucket = _bucket_name()
    # Encode each segment; keep slashes.
    encoded = '/'.join(quote(part, safe='') for part in path.split('/'))
    return f'{base}/storage/v1/object/public/{bucket}/{encoded}'


def supabase_signed_url(name: str, expires_in: int | None = None) -> str:
    """Create a time-limited Supabase signed URL for private buckets."""
    path = _normalize_object_path(name)
    if not path:
        return ''

    ttl = expires_in or int(getattr(settings, 'SUPABASE_SIGNED_URL_TTL', 3600))
    from core.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is None:
        log.warning('Supabase client unavailable; falling back to public URL for %s', path)
        return supabase_public_url(path)

    bucket = _bucket_name()
    try:
        result = client.storage.from_(bucket).create_signed_url(path, ttl)
    except Exception as exc:
        log.warning('supabase_signed_url_failed path=%s err=%s', path, exc)
        return supabase_public_url(path)

    if isinstance(result, dict):
        url = result.get('signedUrl') or result.get('signedURL')
        if url:
            if url.startswith('/'):
                base = (getattr(settings, 'SUPABASE_URL', '') or '').rstrip('/')
                return f'{base}/storage/v1{url}' if base else url
            return str(url)
    return supabase_public_url(path)


def supabase_media_url(name: str) -> str:
    """Return the browser URL for a stored object (public or signed)."""
    if getattr(settings, 'SUPABASE_STORAGE_PUBLIC', True):
        return supabase_public_url(name)
    return supabase_signed_url(name)


class SupabaseMediaStorage(S3Boto3Storage):
    """Upload via S3-compatible API; serve via native Supabase Storage URLs."""

    def url(self, name: str, parameters: Any = None, expire: Any = None, http_method: Any = None) -> str:
        """Prefer native Supabase URLs; fall back to boto signed URLs."""
        native = supabase_media_url(name)
        if native:
            return native
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
