#!/usr/bin/env python3
"""Audit GET/POST actions for guest, buyer, seller, and admin roles.

Usage:
  SECRET_KEY=x DEBUG=true python scripts/role_button_audit.py

Writes a JSON report to /opt/cursor/artifacts/button-audit/report.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
os.environ.setdefault('SECRET_KEY', 'audit-secret')
os.environ.setdefault('DEBUG', 'true')

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django.urls import NoReverseMatch, reverse  # noqa: E402

from core.models import Category, Company, Inventory, Product, UserProfile  # noqa: E402

ARTIFACT_DIR = Path('/opt/cursor/artifacts/button-audit')
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_SETTINGS = dict(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)


@dataclass
class Finding:
    role: str
    action: str
    url: str
    method: str
    status: int
    ok: bool
    detail: str = ''


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]


def _seed_minimal_catalog() -> dict:
    company = Company.objects.create(
        name='Audit Supplier Co',
        legal_name='Audit Supplier Co, S.A.',
        ruc='8-AUDIT-01',
        dv='12',
        business_email='audit@supplier.pa',
        verification_document='companies/verification/audit.pdf',
        verification_status='verified',
    )
    category = Category.objects.create(name='Audit Category')
    product = Product.objects.create(
        company=company,
        category=category,
        name='Audit Widget',
        description='Audit product for button checks.',
        sku='AUD-001',
        unit_price='25.00',
        currency='USD',
        is_active=True,
    )
    Inventory.objects.create(product=product, stock_qty=50, reserved_qty=0)
    company.owner = None
    company.save(update_fields=['owner'])

    buyer = User.objects.create_user('audit_buyer', password='Audit1234!', email='buyer@audit.pa')
    UserProfile.objects.create(user=buyer, role='buyer', email_verificado=True)

    seller = User.objects.create_user('audit_seller', password='Audit1234!', email='seller@audit.pa')
    UserProfile.objects.create(user=seller, role='seller', email_verificado=True)
    company.owner = seller
    company.save(update_fields=['owner'])

    admin = User.objects.create_user('audit_admin', password='Audit1234!', email='admin@audit.pa', is_staff=True)
    UserProfile.objects.create(user=admin, role='admin', email_verificado=True)

    return {
        'product_id': product.pk,
        'company_id': company.pk,
        'buyer': buyer,
        'seller': seller,
        'admin': admin,
    }


def _record(report: AuditReport, *, role, action, url, method, response, ok=None, detail=''):
    status = getattr(response, 'status_code', int(response))
    if ok is None:
        ok = status < 400 or status in (302, 403)
    report.findings.append(
        Finding(role=role, action=action, url=url, method=method, status=status, ok=ok, detail=detail)
    )


def _get_named(report: AuditReport, client: Client, role: str, name: str, *args, **kwargs):
    try:
        url = reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        _record(report, role=role, action=name, url=f'<unresolved:{name}>', method='GET', response=0, ok=False, detail='NoReverseMatch')
        return None
    response = client.get(url)
    _record(report, role=role, action=f'GET {name}', url=url, method='GET', response=response)
    return response


def _post_named(report: AuditReport, client: Client, role: str, name: str, data=None, *args, **kwargs):
    try:
        url = reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        _record(report, role=role, action=name, url=f'<unresolved:{name}>', method='POST', response=0, ok=False, detail='NoReverseMatch')
        return None
    response = client.post(url, data or {})
    ok = response.status_code in (200, 302, 400, 403, 404)
    _record(report, role=role, action=f'POST {name}', url=url, method='POST', response=response, ok=ok)
    return response


def run_audit() -> AuditReport:
    report = AuditReport()
    ctx = _seed_minimal_catalog()
    product_id = ctx['product_id']

    guest = Client()
    buyer_client = Client()
    buyer_client.force_login(ctx['buyer'])
    seller_client = Client()
    seller_client.force_login(ctx['seller'])
    admin_client = Client()
    admin_client.force_login(ctx['admin'])

    guest_gets = [
        'home', 'catalogo_publico', 'login', 'signup_buyer', 'signup_seller',
        'ver_carrito', 'mapa_zlc', 'acerca_tradeflow', 'legal_terminos',
        'legal_privacidad', 'legal_cookies', 'marketplace_deals',
        'marketplace_verified_suppliers', 'marketplace_order_protection',
        'password_reset', 'solicitud_acceso',
    ]
    for name in guest_gets:
        _get_named(report, guest, 'guest', name)
    _get_named(report, guest, 'guest', 'catalogo_producto_detail', pk=product_id)

    buyer_gets = guest_gets + [
        'mi_perfil', 'mis_ordenes', 'mis_cotizaciones', 'checkout',
        'solicitar_cotizacion', 'portal_seller',
    ]
    for name in buyer_gets:
        _get_named(report, buyer_client, 'buyer', name)
    _get_named(report, buyer_client, 'buyer', 'catalogo_producto_detail', pk=product_id)

    seller_gets = [
        'portal_seller', 'seller_mis_productos', 'seller_agregar_producto',
        'seller_mis_ventas', 'seller_plan_consumo', 'seller_predictive_insights',
        'seller_company_qr', 'mi_perfil', 'catalogo_publico', 'home',
    ]
    for name in seller_gets:
        _get_named(report, seller_client, 'seller', name)

    admin_gets = [
        'dashboard', 'admin_saas_dashboard', 'lista_productos', 'nueva_orden_paso1',
        'mis_cotizaciones', 'catalogo_publico', 'home',
    ]
    for name in admin_gets:
        _get_named(report, admin_client, 'admin', name)

    # Button-like POST actions
    _post_named(report, guest, 'guest', 'agregar_al_carrito', {'cantidad': 1}, producto_id=product_id)
    _post_named(report, buyer_client, 'buyer', 'agregar_al_carrito', {'cantidad': 1}, producto_id=product_id)
    _post_named(report, buyer_client, 'buyer', 'logout')
    _post_named(report, seller_client, 'seller', 'logout')
    _post_named(report, admin_client, 'admin', 'logout')

    # Language switcher POST
    for role_name, client in [('guest', guest), ('buyer', buyer_client)]:
        response = client.post('/i18n/setlang/', {'language': 'es', 'next': '/'})
        _record(
            report,
            role=role_name,
            action='POST set_language es',
            url='/i18n/setlang/',
            method='POST',
            response=response,
            ok=response.status_code in (200, 302),
        )

    return report


def main() -> int:
    with override_settings(**AUDIT_SETTINGS):
        report = run_audit()
    payload = {
        'total': len(report.findings),
        'failures': [asdict(f) for f in report.failures],
        'all': [asdict(f) for f in report.findings],
    }
    out = ARTIFACT_DIR / 'report.json'
    out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f'Wrote {out}')
    print(f'Total checks: {payload["total"]} | Failures: {len(payload["failures"])}')
    for failure in report.failures:
        print(f'  FAIL [{failure.role}] {failure.method} {failure.action} -> {failure.status} {failure.detail}')
    return 1 if report.failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
