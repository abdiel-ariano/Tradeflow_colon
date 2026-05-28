#!/usr/bin/env python3
"""
Genera .env local para TradeFlow (no commitear .env).

Uso (Windows PowerShell):
  python scripts/bootstrap_dotenv.py --force `
    --database-url "postgresql://postgres:PASS@db.xxx.supabase.co:5432/postgres" `
    --supabase-url "https://xxx.supabase.co" `
    --supabase-service-key "eyJ..."
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


def build_env_content(
    *,
    secret_key: str,
    database_url: str,
    supabase_url: str,
    supabase_anon: str,
    supabase_service: str,
) -> str:
    return f"""# Generado por scripts/bootstrap_dotenv.py — NO subir a git
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DATABASE_URL={database_url}
DB_SSL=true
DB_SSLMODE=require

SUPABASE_URL={supabase_url}
SUPABASE_ANON_KEY={supabase_anon}
SUPABASE_SERVICE_KEY={supabase_service}
SUPABASE_EMAIL_FUNCTION=send-transactional-email

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=TradeFlow <noreply@tradeflow.pa>
PUBLIC_BASE_URL=http://127.0.0.1:8000

APPLICATION_REVIEW_EMAILS=

REQUIRE_EMAIL_VERIFICATION=true
REQUIRE_APPROVED_APPLICATION=false
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION=true
CHECKOUT_AUTO_APPROVE=false

DASHBOARD_KPI_REVENUE_DELIVERED_ONLY=false
SEED_DEMO_IF_EMPTY=true

GROQ_API_KEY=
"""


def main() -> int:
    parser = argparse.ArgumentParser(description='Crea .env con Supabase + DATABASE_URL.')
    parser.add_argument('--database-url', default=os.environ.get('DATABASE_URL', ''))
    parser.add_argument('--supabase-url', default=os.environ.get('SUPABASE_URL', ''))
    parser.add_argument('--supabase-anon-key', default=os.environ.get('SUPABASE_ANON_KEY', ''))
    parser.add_argument('--supabase-service-key', default=os.environ.get('SUPABASE_SERVICE_KEY', ''))
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    if ENV_PATH.exists() and not args.force:
        print(f'Ya existe {ENV_PATH}. Usa --force para regenerar.')
        return 1

    key = _django_secret_key()
    ENV_PATH.write_text(
        build_env_content(
            secret_key=key,
            database_url=args.database_url.strip(),
            supabase_url=args.supabase_url.strip(),
            supabase_anon=args.supabase_anon_key.strip(),
            supabase_service=args.supabase_service_key.strip(),
        ),
        encoding='utf-8',
    )
    print(f'Listo: {ENV_PATH}')
    print('Ejecuta: python manage.py migrate && python manage.py check_email_env')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
