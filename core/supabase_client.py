"""Singleton Supabase service-role client for server-side API calls.

Used by Edge Function triggers, signed media URLs, and other backends
that must not expose the service key to the browser.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from supabase import Client

log = logging.getLogger('tradeflow.supabase')

_client: Client | None = None
_init_attempted = False


def get_supabase_client() -> Client | None:
    """Return a cached service-role client, or None if unset/unavailable."""
    global _client, _init_attempted
    if _client is not None:
        return _client
    if _init_attempted:
        return None
    _init_attempted = True

    url = (getattr(settings, 'SUPABASE_URL', '') or '').strip()
    key = (getattr(settings, 'SUPABASE_SERVICE_KEY', '') or '').strip()
    if not url or not key:
        log.debug('Supabase no configurado (falta SUPABASE_URL o SUPABASE_SERVICE_KEY)')
        return None

    try:
        from supabase import create_client
    except ImportError:
        log.warning('Paquete supabase no instalado: pip install supabase')
        return None

    try:
        _client = create_client(url, key)
        return _client
    except Exception as exc:
        log.exception('No se pudo crear cliente Supabase: %s', exc)
        return None


def reset_supabase_client() -> None:
    """Clear the cached client (intended for tests)."""
    global _client, _init_attempted
    _client = None
    _init_attempted = False
