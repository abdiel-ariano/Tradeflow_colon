"""Buyer navbar mega menu built from live CFZ categories.

Category panels must link into /catalogo/?categoria= so buyers can jump
from nav to real inventory without emoji placeholders or legacy cards.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.merchandising import buyer_mega_menu_panels
from core.models import Category, Company, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class BuyerMegaMenuTests(TestCase):
    """Assert mega menu panels, branding, and catalog filter wiring."""

    def setUp(self):
        """Log in a buyer with one categorized product in stock."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='buyer_menu',
            email='menu@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        self.company = Company.objects.create(name='Menu Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics & Office')
        Product.objects.create(
            company=self.company,
            category=self.category,
            name='USB Hub',
            sku='USB-1',
            unit_price='10.00',
            currency='USD',
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_buyer_mega_menu_panels_from_db(self):
        """Mega menu panels are built from Category rows and products."""
        panels = buyer_mega_menu_panels()
        self.assertGreaterEqual(len(panels), 1)
        self.assertEqual(panels[0]['category'].name, 'Electronics & Office')
        self.assertGreaterEqual(len(panels[0]['products']), 1)

    def test_navbar_shows_tradeflow_colon_branding(self):
        """Buyer chrome shows TradeFlow Colón, not a generic domain brand."""
        resp = self.client.get(reverse('ver_carrito'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TradeFlow')
        self.assertContains(resp, 'Colón')
        self.assertNotContains(resp, 'TradeFlow.com')

    def test_mega_menu_no_emojis_and_uses_categoria_links(self):
        """Mega menu uses ?categoria= links and omits emoji decoration."""
        resp = self.client.get(reverse('ver_carrito'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'bn-mega-cat')
        self.assertContains(resp, f'?categoria={self.category.pk}')
        self.assertNotContains(resp, '🎽')
        self.assertNotContains(resp, '📱')

    def test_category_filter_returns_products_not_zero(self):
        """Catalog ?categoria= filter returns matching products, not empty."""
        resp = self.client.get(f'{reverse("catalogo_publico")}?categoria={self.category.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'USB Hub')
        self.assertNotContains(resp, 'No products found')

    def test_catalog_uses_product_card_not_legacy_bh_rec(self):
        """Catalog grids use product-card markup, not legacy bh-rec items."""
        resp = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'product-card')
        self.assertNotContains(resp, 'bh-rec-item')
