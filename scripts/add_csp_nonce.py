"""Add CSP nonce attributes to inline script and style tags in templates.

Idempotent: skips tags that already have nonce= or external script src.
Keeps Content-Security-Policy nonce mode workable without unsafe-inline.

Usage:
  python scripts/add_csp_nonce.py
  python scripts/add_csp_nonce.py --dry-run
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
    """Inject nonce attrs into inline script/style tags in one template.

    Returns the number of tags updated (0 if already compliant).
    """
    text = path.read_text(encoding='utf-8')

    def script_replacer(m):
        """Rewrite a matched inline <script> opening tag with nonce."""
        attrs = m.group('attrs').rstrip()
        return f'<script {attrs} {NONCE_ATTR}>' if attrs else f'<script {NONCE_ATTR}>'

    def style_replacer(m):
        """Rewrite a matched <style> opening tag with nonce."""
        attrs = m.group('attrs').rstrip()
        return f'<style {attrs} {NONCE_ATTR}>' if attrs else f'<style {NONCE_ATTR}>'

    new_text, script_changes = SCRIPT_RE.subn(script_replacer, text)
    new_text, style_changes = STYLE_RE.subn(style_replacer, new_text)
    total = script_changes + style_changes

    if total and not dry_run:
        path.write_text(new_text, encoding='utf-8')
    return total


def main():
    """Walk templates/, apply nonce injection, and print a change summary."""
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
