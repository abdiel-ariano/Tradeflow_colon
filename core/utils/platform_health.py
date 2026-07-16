"""Deploy health payload for DB, storage, email, and Supabase flags.

Used by ``/health/`` so Railway and ops can spot CFZ infra drift before
sellers hit checkout failures.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.db import connection

from core.utils.email_delivery import validate_email_infrastructure


def check_database() -> dict:
    """Probe PostgreSQL with SELECT 1 and return latency metadata."""
    started = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
        ok = True
        detail = 'connected'
    except Exception as exc:
        ok = False
        detail = str(exc)[:200]
    return {
        'ok': ok,
        'detail': detail,
        'latency_ms': round((time.perf_counter() - started) * 1000, 1),
    }


def check_storage() -> dict:
    """Report default media backend and whether cloud S3 is in use."""
    using_s3 = 'S3Boto3' in settings.STORAGES.get('default', {}).get('BACKEND', '')
    return {
        'ok': True,
        'backend': settings.STORAGES['default']['BACKEND'],
        'cloud_persistent': using_s3,
        'media_url': getattr(settings, 'MEDIA_URL', '/media/'),
    }


def platform_health_payload() -> dict:
    """Assemble deploy health JSON for DB, storage, email, and Supabase."""
    db = check_database()
    storage = check_storage()
    email_warnings = validate_email_infrastructure()
    # Not a secret — needed to confirm password-reset links point at prod, not localhost.
    public_base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()
    return {
        'status': 'ok' if db['ok'] else 'degraded',
        'version': 'tradeflow-colon',
        'debug': settings.DEBUG,
        'database': db,
        'storage': storage,
        'email': {
            'resend_ready': bool((getattr(settings, 'RESEND_API_KEY', '') or '').strip()),
            'public_base_url': public_base,
            'default_from_email': from_email,
            'warnings': email_warnings,
        },
        'supabase': {
            'database': getattr(settings, 'USING_SUPABASE', False),
            'storage_configured': bool(
                getattr(settings, 'SUPABASE_SERVICE_KEY', '')
                and getattr(settings, 'SUPABASE_URL', '')
            ),
        },
    }
