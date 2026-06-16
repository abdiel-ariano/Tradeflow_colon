"""
Comprueba que la Edge Function de correo existe y responde en Supabase.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings


def edge_function_url(function_name: str | None = None) -> str:
    base = (getattr(settings, 'SUPABASE_URL', '') or '').strip().rstrip('/')
    name = (function_name or getattr(settings, 'SUPABASE_EMAIL_FUNCTION', '') or '').strip()
    if not base or not name:
        return ''
    return f'{base}/functions/v1/{name}'


def probe_edge_function(*, dry_run: bool = True) -> dict:
    """
    Llama a la Edge Function con un POST mínimo.

    dry_run=True: no envía correo real (la función actual no tiene modo dry-run,
    así que usamos un asunto de prueba solo si dry_run es False).
    """
    url = edge_function_url()
    service_key = (getattr(settings, 'SUPABASE_SERVICE_KEY', '') or '').strip()
    function_name = getattr(settings, 'SUPABASE_EMAIL_FUNCTION', 'send-transactional-email')

    result = {
        'ok': False,
        'url': url,
        'function': function_name,
        'status': None,
        'detail': '',
        'hint': '',
    }

    if not url:
        result['detail'] = 'missing_supabase_url_or_function'
        result['hint'] = 'Define SUPABASE_URL y SUPABASE_EMAIL_FUNCTION en Railway.'
        return result
    if not service_key:
        result['detail'] = 'missing_service_key'
        result['hint'] = 'Define SUPABASE_SERVICE_KEY (service_role) en Railway.'
        return result

    payload = {
        'to': getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', 'tradeflowcolon@gmail.com'),
        'subject': 'TradeFlow edge probe',
        'html': '<p>Probe</p>',
        'text': 'Probe',
        'type': 'transactional',
    }
    if dry_run:
        # HEAD no está soportado; un POST vacío inválido basta para detectar 404 vs 400.
        payload = {'probe': True}

    body = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result['status'] = resp.status
            raw = resp.read().decode('utf-8', errors='replace')[:500]
            result['detail'] = raw
            result['ok'] = 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        result['status'] = exc.code
        try:
            result['detail'] = exc.read().decode('utf-8', errors='replace')[:500]
        except Exception:
            result['detail'] = str(exc)
        if exc.code == 404 or 'not_found' in (result['detail'] or '').lower():
            result['hint'] = (
                f'La función "{function_name}" NO está desplegada en este proyecto Supabase. '
                'Despliega con: supabase functions deploy send-transactional-email '
                'o GitHub Actions → Deploy Supabase Edge Functions → Run workflow.'
            )
        elif exc.code == 500 and 'gmail_not_configured' in (result['detail'] or '').lower():
            result['hint'] = 'Desplegada pero faltan secrets GMAIL_USER / GMAIL_APP_PASSWORD en Supabase.'
        elif exc.code == 400:
            result['ok'] = True  # existe; payload de probe inválido es esperado
            result['hint'] = 'La función existe (respondió 400 al probe). Prueba un envío real.'
    except Exception as exc:
        result['detail'] = str(exc)[:500]
        result['hint'] = 'Error de red al llamar Supabase. Revisa SUPABASE_URL.'

    return result
