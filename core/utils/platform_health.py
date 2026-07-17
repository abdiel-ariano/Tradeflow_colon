"""Payload de salud de deploy para BD, storage, correo y flags Supabase.

Usado por ``/health/`` para que Railway y ops detecten deriva de infra ZLC
antes de que los vendedores fallen en checkout.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.db import connection

from core.utils.email_delivery import validate_email_infrastructure


def check_database() -> dict:
    """Sondea PostgreSQL con SELECT 1 y devuelve metadatos de latencia."""
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
    """Reporta el backend de media por defecto y si se usa S3 en la nube."""
    using_s3 = 'S3Boto3' in settings.STORAGES.get('default', {}).get('BACKEND', '')
    return {
        'ok': True,
        'backend': settings.STORAGES['default']['BACKEND'],
        'cloud_persistent': using_s3,
        'media_url': getattr(settings, 'MEDIA_URL', '/media/'),
    }


def platform_health_payload() -> dict:
    """Arma el JSON de salud de deploy para BD, storage, correo y Supabase."""
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
