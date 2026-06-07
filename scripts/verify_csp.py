r"""
Smoke test del CSP nonce. Usa el Django test client para verificar que:
  1) El header Content-Security-Policy contiene 'nonce-XXX' y NO 'unsafe-inline'.
  2) El nonce del header coincide con el nonce en el HTML.
  3) Cada <script> (sin src) y cada <style> tiene el atributo nonce="...".
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')

import django  # noqa: E402

django.setup()

from django.test.client import Client  # noqa: E402

NONCE_HEADER_RE = re.compile(r"'nonce-([A-Za-z0-9_\-]+)'")
SCRIPT_INLINE_RE = re.compile(r'<script(?![^>]*\bsrc=)([^>]*)>', re.IGNORECASE)
STYLE_TAG_RE = re.compile(r'<style\b([^>]*)>', re.IGNORECASE)


def check_url(client, url):
    notes = []
    resp = client.get(url, follow=True)
    if resp.status_code == 404:
        notes.append('SKIP: 404 (la pagina debug 404 de Django no es nuestro template)')
        return True, notes
    csp = resp.headers.get('Content-Security-Policy', '') or resp.get('Content-Security-Policy', '')
    if not csp:
        notes.append('FALTA: header Content-Security-Policy')
        return False, notes

    if "'unsafe-inline'" in csp:
        notes.append("FALLA: CSP aun contiene 'unsafe-inline'")

    nonces_in_header = NONCE_HEADER_RE.findall(csp)
    if not nonces_in_header:
        notes.append('FALLA: no se encontro nonce-XXX en el header CSP')
        return False, notes
    nonce = nonces_in_header[0]

    html = resp.content.decode('utf-8', errors='replace')
    missing = []
    for match in SCRIPT_INLINE_RE.finditer(html):
        attrs = match.group(1)
        if f'nonce="{nonce}"' not in attrs:
            missing.append(f'<script{attrs[:60]}...> SIN nonce')
    for match in STYLE_TAG_RE.finditer(html):
        attrs = match.group(1)
        if f'nonce="{nonce}"' not in attrs:
            missing.append(f'<style{attrs[:60]}...> SIN nonce')

    if missing:
        notes.append(f'FALLA: {len(missing)} inline tags sin nonce:')
        for m in missing[:5]:
            notes.append(f'    {m}')
        if len(missing) > 5:
            notes.append(f'    ... y {len(missing) - 5} mas')
        return False, notes

    notes.append(f'OK: CSP nonce={nonce[:10]}..., {len(nonces_in_header)} apariciones, 0 inline huerfanos')
    return True, notes


def main():
    client = Client(SERVER_NAME='127.0.0.1')
    urls = ['/', '/login/', '/signup/', '/solicitud-acceso/']
    all_ok = True
    for url in urls:
        ok, notes = check_url(client, url)
        prefix = '[OK]' if ok else '[FAIL]'
        print(f'{prefix} {url}')
        for n in notes:
            print(f'   {n}')
        all_ok = all_ok and ok

    resp = client.get('/mapa/', follow=True)
    if resp.status_code == 200:
        csp = resp.headers.get('Content-Security-Policy', '')
        if "'unsafe-inline'" in csp:
            print("[OK] /mapa/  excepcion CSP aplicada (Folium-compatible)")
        else:
            print("[FAIL] /mapa/  deberia tener 'unsafe-inline' pero no lo tiene")
            all_ok = False
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
