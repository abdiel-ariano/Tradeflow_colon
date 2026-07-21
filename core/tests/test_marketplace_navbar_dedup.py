"""Marketplace marketing pages must render a single Alibaba navbar."""
from __future__ import annotations

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    EXPO_DEMO_MODE=False,
)
class MarketplaceNavbarDedupTests(TestCase):
    """Guests on deals/verified/about/etc. get one cat-catalog-nav only."""

    def setUp(self):
        self.client = Client()
        translation.activate('en')

    def tearDown(self):
        translation.deactivate()

    def _assert_single_marketplace_nav(self, path: str):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        body = resp.content.decode('utf-8')
        count = body.count('id="cat-catalog-nav"')
        self.assertEqual(
            count,
            1,
            f'{path} expected one marketplace navbar, got {count}',
        )

    def test_deals_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_deals'))

    def test_verified_suppliers_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_verified_suppliers'))

    def test_order_protection_single_nav(self):
        self._assert_single_marketplace_nav(reverse('marketplace_order_protection'))

    def test_about_single_nav(self):
        self._assert_single_marketplace_nav(reverse('acerca_tradeflow'))

    def test_home_and_catalog_single_nav(self):
        self._assert_single_marketplace_nav(reverse('home'))
        self._assert_single_marketplace_nav(reverse('catalogo_publico'))

    def test_map_and_legal_single_nav(self):
        self._assert_single_marketplace_nav(reverse('mapa_zlc'))
        self._assert_single_marketplace_nav(reverse('legal_privacidad'))

    def test_es_locale_verified_single_nav(self):
        """Spanish-prefixed URLs must not reintroduce a second navbar."""
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'
        self._assert_single_marketplace_nav('/es/verified-suppliers/')
        self._assert_single_marketplace_nav('/es/order-protection/')
