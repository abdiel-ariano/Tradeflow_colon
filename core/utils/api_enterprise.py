"""Autentica y audita claves API enterprise con acceso por alcance (scopes)."""
from __future__ import annotations

import hashlib
import hmac
import time

from django.core.cache import cache
from django.http import JsonResponse

from core.enterprise_models import ApiAuditLog, ApiKey
from core.utils.client_ip import get_client_ip


SCOPE_INVENTORY_READ = 'inventory.read'
SCOPE_PRICING_WRITE = 'pricing.write'
SCOPE_WEBHOOKS = 'webhooks.receive'


def hash_api_key(raw: str) -> str:
    """Devuelve un hash estable de la clave API en crudo para búsqueda en almacenamiento."""
    return hashlib.sha256(raw.encode()).hexdigest()


def authenticate_api_key(request) -> tuple[ApiKey | None, JsonResponse | None]:
    """Resuelve un header de clave API a empresa y scopes, o None."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, JsonResponse({'error': 'missing_token'}, status=401)
    raw = auth[7:].strip()
    if not raw.startswith('tf_live_') or len(raw) < 20:
        return None, JsonResponse({'error': 'invalid_token'}, status=401)
    digest = hash_api_key(raw)
    key = ApiKey.objects.filter(key_hash=digest, is_active=True).select_related('company').first()
    if not key:
        return None, JsonResponse({'error': 'invalid_token'}, status=401)

    rl_key = f'tf_api_rl:{key.pk}:{int(time.time()) // 60}'
    count = cache.get(rl_key, 0)
    if count >= key.rate_limit_per_minute:
        return None, JsonResponse({'error': 'rate_limit'}, status=429)
    cache.set(rl_key, count + 1, 65)

    return key, None


def require_scope(key: ApiKey, scope: str) -> bool:
    """Lanza si la clave autenticada carece del alcance requerido."""
    scopes = key.scopes or []
    return scope in scopes or '*' in scopes


def audit_api_call(key: ApiKey | None, company, request, status_code: int):
    """Persiste una fila de auditoría API para la llamada enterprise."""
    ApiAuditLog.objects.create(
        api_key=key,
        company=company,
        method=request.method[:10],
        path=request.path[:255],
        status_code=status_code,
        ip_address=get_client_ip(request),
    )
