#!/usr/bin/env python3
"""
Genera .env local para TradeFlow (no commitear .env).

Uso (Windows PowerShell):
  python scripts/bootstrap_dotenv.py --resend-key "re_xxxxxxxx"

O con variable de entorno:
  $env:RESEND_API_KEY="re_xxxxxxxx"
  python scripts/bootstrap_dotenv.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / '.env'


def _django_secret_key() -> str:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
    sys.path.insert(0, str(ROOT))
    from django.core.management.utils import get_random_secret_key

    return get_random_secret_key()


def build_env_content(*, secret_key: str, resend_key: str) -> str:
    key = resend_key.strip().replace('"', '')
    review = os.environ.get('APPLICATION_REVIEW_EMAIL', 'onboarding@resend.dev').strip()
    return f"""# Generado por scripts/bootstrap_dotenv.py — NO subir a git
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DATABASE_URL=
DB_SSL=False
DB_SSLMODE=require

# Resend (https://resend.com/api-keys)
RESEND_API_KEY={key}

DEFAULT_FROM_EMAIL=TradeFlow <onboarding@resend.dev>
PUBLIC_BASE_URL=http://127.0.0.1:8000

APPLICATION_REVIEW_EMAILS={review}

REQUIRE_EMAIL_VERIFICATION=true
REQUIRE_APPROVED_APPLICATION=false
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION=true
CHECKOUT_AUTO_APPROVE=false

DASHBOARD_KPI_REVENUE_DELIVERED_ONLY=false
SEED_DEMO_IF_EMPTY=true

GROQ_API_KEY=
"""


def main() -> int:
    parser = argparse.ArgumentParser(description='Crea .env local con Resend y SECRET_KEY.')
    parser.add_argument(
        '--resend-key',
        default=os.environ.get('RESEND_API_KEY', ''),
        help='API key de Resend (re_...). O variable RESEND_API_KEY.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Sobrescribir .env existente',
    )
    args = parser.parse_args()

    if ENV_PATH.exists() and not args.force:
        print(f'Ya existe {ENV_PATH}. Usa --force para regenerar.')
        return 1

    if not args.resend_key:
        print(
            'Falta RESEND_API_KEY. Ejemplo:\n'
            '  python scripts/bootstrap_dotenv.py --resend-key "re_xxxxxxxx"'
        )
        return 1

    key = _django_secret_key()
    ENV_PATH.write_text(
        build_env_content(secret_key=key, resend_key=args.resend_key),
        encoding='utf-8',
    )
    print(f'Listo: {ENV_PATH}')
    print(f'SECRET_KEY={key[:20]}...')
    print('Reinicia runserver y ejecuta: python manage.py check_email_env')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
