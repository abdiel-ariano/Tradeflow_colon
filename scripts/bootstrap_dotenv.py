#!/usr/bin/env python3
"""
Genera .env local para TradeFlow (no commitear .env).

Uso (Windows PowerShell):
  python scripts/bootstrap_dotenv.py --app-password "xxxx xxxx xxxx xxxx"

O con variable de entorno (no deja la clave en el historial del script):
  $env:GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
  python scripts/bootstrap_dotenv.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / '.env'

DEFAULT_GMAIL_USER = 'tradeflowcolon@gmail.com'


def _django_secret_key() -> str:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
    sys.path.insert(0, str(ROOT))
    from django.core.management.utils import get_random_secret_key

    return get_random_secret_key()


def build_env_content(*, secret_key: str, app_password: str) -> str:
    pw = app_password.strip()
    user = os.environ.get('GMAIL_USER', DEFAULT_GMAIL_USER).strip() or DEFAULT_GMAIL_USER
    return f"""# Generado por scripts/bootstrap_dotenv.py — NO subir a git
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DATABASE_URL=
DB_SSL=False
DB_SSLMODE=require

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER={user}
EMAIL_HOST_PASSWORD={pw}
EMAIL_FORCE_SMTP=false

DEFAULT_FROM_EMAIL=TradeFlow Colon <{user}>
PUBLIC_BASE_URL=http://127.0.0.1:8000

APPLICATION_REVIEW_EMAILS={user}

REQUIRE_EMAIL_VERIFICATION=true
REQUIRE_APPROVED_APPLICATION=false
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION=true
CHECKOUT_AUTO_APPROVE=false

DASHBOARD_KPI_REVENUE_DELIVERED_ONLY=false
SEED_DEMO_IF_EMPTY=true

GROQ_API_KEY=
"""


def main() -> int:
    parser = argparse.ArgumentParser(description='Crea .env local con Gmail y SECRET_KEY.')
    parser.add_argument(
        '--app-password',
        default=os.environ.get('GMAIL_APP_PASSWORD', ''),
        help='App Password de Google (16 caracteres). O variable GMAIL_APP_PASSWORD.',
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

    if not args.app_password:
        print(
            'Falta App Password. Ejemplo:\n'
            '  python scripts/bootstrap_dotenv.py --app-password "xxxx xxxx xxxx xxxx"'
        )
        return 1

    key = _django_secret_key()
    ENV_PATH.write_text(
        build_env_content(secret_key=key, app_password=args.app_password),
        encoding='utf-8',
    )
    print(f'Listo: {ENV_PATH}')
    print(f'SECRET_KEY={key[:20]}...')
    print(f'EMAIL_HOST_USER={DEFAULT_GMAIL_USER}')
    print('Reinicia runserver y ejecuta: python manage.py verify_integrations --email', DEFAULT_GMAIL_USER)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
