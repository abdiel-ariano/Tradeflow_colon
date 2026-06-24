r"""
Anade `nonce="{{ csp_nonce }}"` a todos los <script> y <style> inline en
las plantillas Django, de forma idempotente.

Uso:
  python scripts/add_csp_nonce.py                # actualiza in-place
  python scripts/add_csp_nonce.py --dry-run     # solo reporta
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'templates'
NONCE_ATTR = 'nonce="{{ csp_nonce }}"'

SCRIPT_RE = re.compile(
    r'<script\b(?P<attrs>(?:(?!>)(?!\bsrc\s*=)(?!\bnonce\s*=).)*)>',
    re.IGNORECASE | re.DOTALL,
)
STYLE_RE = re.compile(
    r'<style\b(?P<attrs>(?:(?!>)(?!\bnonce\s*=).)*)>',
    re.IGNORECASE | re.DOTALL,
)


def process_file(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding='utf-8')

    def script_replacer(m):
        attrs = m.group('attrs').rstrip()
        return f'<script {attrs} {NONCE_ATTR}>' if attrs else f'<script {NONCE_ATTR}>'

    def style_replacer(m):
        attrs = m.group('attrs').rstrip()
        return f'<style {attrs} {NONCE_ATTR}>' if attrs else f'<style {NONCE_ATTR}>'

    new_text, script_changes = SCRIPT_RE.subn(script_replacer, text)
    new_text, style_changes = STYLE_RE.subn(style_replacer, new_text)
    total = script_changes + style_changes

    if total and not dry_run:
        path.write_text(new_text, encoding='utf-8')
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not TEMPLATES_DIR.is_dir():
        print(f'ERROR: no se encontro {TEMPLATES_DIR}', file=sys.stderr)
        return 1

    total_changes = 0
    files_changed = 0
    for path in sorted(TEMPLATES_DIR.rglob('*.html')):
        changes = process_file(path, args.dry_run)
        if changes:
            files_changed += 1
            total_changes += changes
            print(f'{"[dry]" if args.dry_run else "[ok ]"} {changes:>3} cambios  {path.relative_to(TEMPLATES_DIR.parent)}')

    print(f'\nResumen: {total_changes} tags actualizados en {files_changed} archivos.')
    if args.dry_run:
        print('(dry-run: no se escribio nada).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
