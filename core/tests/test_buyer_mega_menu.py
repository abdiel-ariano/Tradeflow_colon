"""Buyer navbar mega menu — categorías reales, sin emojis, enlaces ?categoria=."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.merchandising import buyer_mega_menu_panels
from core.models import Category, Company, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class BuyerMegaMenuTests(TestCase):
    def setUp(self):
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
        panels = buyer_mega_menu_panels()
        self.assertGreaterEqual(len(panels), 1)
        self.assertEqual(panels[0]['category'].name, 'Electronics & Office')
        self.assertGreaterEqual(len(panels[0]['products']), 1)

    def test_navbar_shows_tradeflow_colon_branding(self):
        resp = self.client.get('/tienda/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TradeFlow')
        self.assertContains(resp, 'Colón')
        self.assertNotContains(resp, 'TradeFlow.com')

    def test_mega_menu_no_emojis_and_uses_categoria_links(self):
        resp = self.client.get('/tienda/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'bn-mega-cat')
        self.assertContains(resp, f'?categoria={self.category.pk}')
        self.assertNotContains(resp, '🎽')
        self.assertNotContains(resp, '📱')

    def test_category_filter_returns_products_not_zero(self):
        resp = self.client.get(f'/tienda/?categoria={self.category.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'USB Hub')
        self.assertNotContains(resp, 'No products found')

    def test_recommended_uses_tf_pcard_not_bh_rec_item(self):
        resp = self.client.get('/tienda/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'tf-pcard')
        self.assertNotContains(resp, 'bh-rec-item')
