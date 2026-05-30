"""
Health checks y validación de plataforma para deploy / observabilidad.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.db import connection

from core.utils.email_delivery import validate_email_infrastructure


def check_database() -> dict:
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
    using_s3 = 'S3Boto3' in settings.STORAGES.get('default', {}).get('BACKEND', '')
    return {
        'ok': True,
        'backend': settings.STORAGES['default']['BACKEND'],
        'cloud_persistent': using_s3,
        'media_url': getattr(settings, 'MEDIA_URL', '/media/'),
    }


def platform_health_payload() -> dict:
    db = check_database()
    storage = check_storage()
    email_warnings = validate_email_infrastructure()
    return {
        'status': 'ok' if db['ok'] else 'degraded',
        'version': 'tradeflow-colon',
        'debug': settings.DEBUG,
        'database': db,
        'storage': storage,
        'email': {
            'smtp_ready': getattr(settings, 'EMAIL_USE_REAL_SMTP', False),
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
