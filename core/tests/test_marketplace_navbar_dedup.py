"""Marketplace marketing pages must render a single Alibaba navbar."""
from __future__ import annotations

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
)
class MarketplaceNavbarDedupTests(TestCase):
    """Guests on deals/verified/about/etc. get one cat-catalog-nav only."""

    def setUp(self):
        self.client = Client()

    def _assert_single_marketplace_nav(self, path: str):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        body = resp.content.decode('utf-8')
        self.assertEqual(
            body.count('id="cat-catalog-nav"'),
            1,
            f'{path} expected one marketplace navbar, got {body.count("id=\"cat-catalog-nav\"")}',
        )

    def test_deals_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_deals'))

    def test_verified_suppliers_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_verified_suppliers'))

    def test_order_protection_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_order_protection'))

    def test_about_single_nav(self):
        self._assert_single_marketplace_nav(reverse('acerca_tradeflow'))
