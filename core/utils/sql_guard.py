"""Allowlist guard for staff analytics SQL (SELECT / WITH only)."""
from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|'
    r'COPY|EXECUTE|CALL|MERGE|REPLACE|ATTACH|DETACH|VACUUM|PRAGMA|'
    r'SET\s+ROLE|SET\s+SESSION|INTO\s+OUTFILE|LOAD\s+DATA)\b',
    re.IGNORECASE,
)


def assert_readonly_sql(sql: str) -> str:
    """Normalize and validate that ``sql`` is a single read-only statement.

    Raises ``ValueError`` when the statement is empty, multi-statement,
    or not a SELECT/WITH query.
    """
    cleaned = (sql or '').strip()
    if not cleaned:
        raise ValueError('La consulta SQL está vacía.')
    # Strip a single trailing semicolon; reject any others (multi-statement).
    if cleaned.endswith(';'):
        cleaned = cleaned[:-1].rstrip()
    if ';' in cleaned:
        raise ValueError('Solo se permite una sentencia SQL de lectura.')
    head = cleaned.lstrip().upper()
    if not (head.startswith('SELECT') or head.startswith('WITH')):
        raise ValueError('Solo se permiten consultas SELECT (o WITH … SELECT).')
    if _FORBIDDEN.search(cleaned):
        raise ValueError('La consulta contiene palabras clave no permitidas.')
    return cleaned
