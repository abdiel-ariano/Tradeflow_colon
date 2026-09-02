#!/usr/bin/env python3
"""Scan templates and static JS for likely hardcoded user-visible strings.

Usage:
  python scripts/i18n_audit.py
  python scripts/i18n_audit.py --strict

Exit code 0 when no issues (or only allowed patterns); 1 when findings exist.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_DIRS = (
    ROOT / 'templates',
    ROOT / 'static' / 'js',
)

SKIP_PARTS = {
    'node_modules',
    'staticfiles',
    'admin-saas',
    '.min.',
    'vendor',
}

SPANISH_HINT = re.compile(r'[áéíóúñÁÉÍÓÚÑ¿¡]')
ENGLISH_UI = re.compile(
    r'\b(?:Loading|Save|Cancel|Delete|Edit|Search|Filter|Previous|Next|'
    r'Pending|Processing|Completed|Settings|Dashboard|Sign out|Sign in|'
    r'Create account|No results|Not available)\b',
    re.I,
)

TEMPLATE_TEXT = re.compile(
    r'>([^<{%][^<]{2,120})<',
)
TEMPLATE_ATTR = re.compile(
    r'\b(?:placeholder|title|aria-label|alt)=["\']([^"\']{3,120})["\']',
)
JS_STRING = re.compile(
    r"""['"]([^'"]{4,120})['"]""",
)

ALLOWED_SNIPPETS = (
    'TradeFlow',
    'Colón',
    'material-symbols',
    'csrfmiddlewaretoken',
    'DELETE',
    'DEMO',
    'USD',
    'PA',
    'ES',
    'EN',
    'TF',
    'http',
    'www.',
    '@',
    'rgba(',
    '#',
    'bootstrap',
    'chart.js',
    'application/json',
    'non-json',
    'poll_failed',
    'toggle_failed',
)


def _allowed(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.isdigit():
        return True
    if re.fullmatch(r'[A-Z0-9_\-./:?=&%+#]+', stripped):
        return True
    for token in ALLOWED_SNIPPETS:
        if token in stripped:
            return True
    return False


def _has_i18n_nearby(lines: list[str], idx: int) -> bool:
    window = '\n'.join(lines[max(0, idx - 2): idx + 3])
    return '{% trans' in window or '{% blocktrans' in window or '_(' in window


def scan_file(path: Path, strict: bool) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return findings
    lines = text.splitlines()
    suffix = path.suffix.lower()

    if suffix == '.html':
        for i, line in enumerate(lines):
            if '{% trans' in line or '{% blocktrans' in line:
                continue
            for match in TEMPLATE_ATTR.finditer(line):
                value = match.group(1).strip()
                if _allowed(value) or _has_i18n_nearby(lines, i):
                    continue
                if SPANISH_HINT.search(value) or (strict and ENGLISH_UI.search(value)):
                    findings.append(f'{path}:{i + 1}: attr {value!r}')
            for match in TEMPLATE_TEXT.finditer(line):
                value = re.sub(r'\s+', ' ', match.group(1)).strip()
                if not value or value.startswith('{%') or _allowed(value):
                    continue
                if '{' in value and '}' in value:
                    continue
                if _has_i18n_nearby(lines, i):
                    continue
                if SPANISH_HINT.search(value) or (strict and ENGLISH_UI.search(value)):
                    findings.append(f'{path}:{i + 1}: text {value!r}')

    if suffix == '.js' and 'static/js' in str(path):
        for i, line in enumerate(lines):
            if 'TF_I18N' in line or 'i18n(' in line:
                continue
            for match in JS_STRING.finditer(line):
                value = match.group(1).strip()
                if _allowed(value):
                    continue
                if SPANISH_HINT.search(value) or (strict and ENGLISH_UI.search(value)):
                    if any(tok in line for tok in ('console.', 'Error(', 'throw ')):
                        continue
                    findings.append(f'{path}:{i + 1}: js {value!r}')
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit hardcoded UI strings')
    parser.add_argument('--strict', action='store_true', help='Also flag common English UI words')
    args = parser.parse_args()

    all_findings: list[str] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file():
                continue
            if any(part in str(path) for part in SKIP_PARTS):
                continue
            if path.suffix.lower() not in {'.html', '.js'}:
                continue
            all_findings.extend(scan_file(path, args.strict))

    if all_findings:
        print(f'Found {len(all_findings)} potential hardcoded UI strings:')
        for item in all_findings[:200]:
            print(item)
        if len(all_findings) > 200:
            print(f'... and {len(all_findings) - 200} more')
        return 1

    print('No obvious hardcoded Spanish/English UI strings detected.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
