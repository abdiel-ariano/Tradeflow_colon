#!/usr/bin/env python3
"""Live-server button/page audit with login sessions and error detection."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

BASE = 'http://127.0.0.1:8000'
ARTIFACT = Path('/opt/cursor/artifacts/button-audit')
ARTIFACT.mkdir(parents=True, exist_ok=True)

ERROR_PATTERNS = [
    re.compile(r'<title>Server Error \(500\)</title>', re.I),
    re.compile(r'<h1>Server Error \(500\)</h1>', re.I),
    re.compile(r'Traceback \(most recent call last\)', re.I),
    re.compile(r'NoReverseMatch at', re.I),
    re.compile(r'OperationalError at', re.I),
    re.compile(r'AttributeError at', re.I),
    re.compile(r'TemplateSyntaxError at', re.I),
]

ROLE_PAGES = {
    'guest': [
        '/', '/catalogo/', '/login/', '/signup/comprador/', '/carrito/',
        '/mapa/', '/acerca/', '/verified-suppliers/', '/deals/',
    ],
    'buyer': [
        '/perfil/', '/mis-ordenes/', '/mis-cotizaciones/', '/checkout/', '/carrito/',
    ],
    'seller': [
        '/mi-tienda/', '/mi-tienda/productos/', '/mi-tienda/productos/nuevo/',
        '/mi-tienda/ventas/', '/mi-tienda/plan/', '/mi-tienda/cotizaciones/',
        '/mi-tienda/configuracion/', '/perfil/',
    ],
    'admin': [
        '/dashboard/', '/saas/', '/productos/', '/ordenes/', '/empresas/',
        '/panel/applications/',
    ],
}

CREDENTIALS = {
    'buyer': ('demo_buyer', 'Demo1234!'),
    'seller': ('demo_seller', 'Demo1234!'),
    'admin': ('demo_admin', 'Demo1234!'),
}


def login(session: requests.Session, username: str, password: str) -> bool:
    r = session.get(f'{BASE}/login/')
    if r.status_code >= 500:
        return False
    token = session.cookies.get('csrftoken')
    if not token:
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
        token = m.group(1) if m else ''
    resp = session.post(
        f'{BASE}/login/',
        data={
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': token,
            'next': '/',
        },
        headers={'Referer': f'{BASE}/login/'},
        allow_redirects=False,
    )
    return resp.status_code in (302, 303)


def audit_role(role: str, paths: list[str], session: requests.Session | None = None) -> list[dict]:
    findings = []
    sess = session or requests.Session()
    for path in paths:
        url = BASE + path
        try:
            resp = sess.get(url, timeout=20, allow_redirects=True)
        except requests.RequestException as exc:
            findings.append({'role': role, 'path': path, 'ok': False, 'status': 0, 'detail': str(exc)})
            continue
        body = resp.text
        err = next((p.pattern for p in ERROR_PATTERNS if p.search(body)), None)
        ok = resp.status_code < 500 and err is None
        item = {
            'role': role,
            'path': path,
            'final_url': resp.url,
            'ok': ok,
            'status': resp.status_code,
            'detail': err or '',
        }
        findings.append(item)
        if not ok:
            shot = ARTIFACT / f'fail-{role}-{path.strip("/").replace("/", "_") or "root"}.html'
            shot.write_text(body[:200000], encoding='utf-8')
    return findings


def main() -> int:
    all_findings: list[dict] = []
    all_findings.extend(audit_role('guest', ROLE_PAGES['guest']))

    for role, creds in CREDENTIALS.items():
        sess = requests.Session()
        if not login(sess, *creds):
            all_findings.append({'role': role, 'path': '/login/', 'ok': False, 'status': 0, 'detail': 'login failed'})
            continue
        all_findings.extend(audit_role(role, ROLE_PAGES[role], sess))

    failures = [f for f in all_findings if not f['ok']]
    report = {'total': len(all_findings), 'failures': failures, 'all': all_findings}
    (ARTIFACT / 'live-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'total': report['total'], 'failures': len(failures)}, indent=2))
    for f in failures:
        print(f"FAIL [{f['role']}] {f.get('path')} status={f.get('status')} {f.get('detail')}")
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
