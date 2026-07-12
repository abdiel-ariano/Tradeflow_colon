"""
Normalize DATABASE_URL for Supabase/Railway deploys.

Common production failures:
- Pooler host with user ``postgres`` instead of ``postgres.<project-ref>``
- Password special characters breaking URL parsing
- Stale password after Supabase reset

Supports component vars (password without URL encoding):
  SUPABASE_DB_HOST, SUPABASE_DB_PORT, SUPABASE_DB_NAME,
  SUPABASE_DB_USER, SUPABASE_DB_PASSWORD, SUPABASE_PROJECT_REF
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import quote, unquote, urlparse, urlunparse

log = logging.getLogger('tradeflow.database')

_POOLER_HOST_RE = re.compile(r'pooler\.supabase\.com', re.I)
_SUPABASE_URL_REF_RE = re.compile(r'https?://([a-z0-9]{10,})\.supabase\.co', re.I)


def _clean_env(value: str) -> str:
    value = (value or '').strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        value = value[1:-1]
    return value.strip()


def infer_supabase_project_ref() -> str | None:
    """Infer supabase project ref."""
    explicit = _clean_env(os.environ.get('SUPABASE_PROJECT_REF', ''))
    if explicit:
        return explicit
    supabase_url = _clean_env(os.environ.get('SUPABASE_URL', ''))
    match = _SUPABASE_URL_REF_RE.search(supabase_url)
    return match.group(1) if match else None


def _pooler_username(user: str, project_ref: str | None) -> str:
    if not project_ref or not user:
        return user
    if user == 'postgres':
        return f'postgres.{project_ref}'
    if user.startswith('postgres.') and '.' not in user[len('postgres.'):]:
        return user
    if user == project_ref:
        return f'postgres.{project_ref}'
    return user


def build_database_url_from_components() -> str:
    """Build database url from components."""
    host = _clean_env(os.environ.get('SUPABASE_DB_HOST', ''))
    password = _clean_env(os.environ.get('SUPABASE_DB_PASSWORD', ''))
    if not host or not password:
        return ''

    port = _clean_env(os.environ.get('SUPABASE_DB_PORT', '')) or '5432'
    name = _clean_env(os.environ.get('SUPABASE_DB_NAME', '')) or 'postgres'
    user = _clean_env(os.environ.get('SUPABASE_DB_USER', '')) or 'postgres'
    project_ref = infer_supabase_project_ref()
    if _POOLER_HOST_RE.search(host):
        user = _pooler_username(user, project_ref)

    safe_password = quote(password, safe='')
    return f'postgresql://{user}:{safe_password}@{host}:{port}/{name}'


def normalize_database_url(raw_url: str) -> str:
    """
    Return a DATABASE_URL safe for dj-database-url.parse().

    Applies pooler username correction and optional DATABASE_PASSWORD override.
    """
    url = _clean_env(raw_url)
    if not url:
        url = build_database_url_from_components()
    if not url:
        return ''

    password_override = _clean_env(os.environ.get('DATABASE_PASSWORD', ''))
    project_ref = infer_supabase_project_ref()

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return url

    username = unquote(parsed.username or '')
    password = password_override or unquote(parsed.password or '')
    hostname = parsed.hostname or ''

    if _POOLER_HOST_RE.search(hostname):
        fixed_user = _pooler_username(username, project_ref)
        if fixed_user != username:
            log.warning(
                'DATABASE_URL pooler username adjusted %s → %s (Supabase session pooler)',
                username,
                fixed_user,
            )
            username = fixed_user

    netloc = hostname
    if parsed.port:
        netloc = f'{hostname}:{parsed.port}'
    if username:
        auth = username
        if password:
            auth = f'{username}:{quote(password, safe="")}'
        netloc = f'{auth}@{netloc}'

    normalized = urlunparse((
        parsed.scheme,
        netloc,
        parsed.path or '/postgres',
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return normalized


def database_connection_hint(error: Exception) -> str:
    """Human-readable Railway/Supabase fix steps for deploy logs."""
    message = str(error).lower()
    lines = [
        'Database connection failed.',
    ]
    if 'password authentication failed' in message:
        lines.extend([
            '1. Supabase → Settings → Database → reset database password.',
            '2. Railway → Variables → update DATABASE_URL with the new password.',
            '3. For pooler URLs use user postgres.<project-ref>, not postgres alone.',
            '   Tip: set SUPABASE_URL=https://<ref>.supabase.co so we auto-fix the username.',
            '4. Or set SUPABASE_DB_PASSWORD (and host/port) without embedding special chars in the URL.',
        ])
    elif 'could not connect' in message or 'timeout' in message:
        lines.extend([
            '1. Confirm Supabase project is not paused.',
            '2. Use the pooler host from Supabase → Connect → Session pooler.',
            '3. Set DB_SSL=true and DB_SSLMODE=require.',
        ])
    else:
        lines.append(str(error)[:240])
    return '\n'.join(lines)
