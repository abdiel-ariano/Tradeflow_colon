"""Tarjeta de producto unificada y vista pública de detalle."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class ProductCardUnifiedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='CFZ Demo Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Unified Widget',
            sku='UW-001',
            unit_price='99.99',
            currency='USD',
            is_active=True,
            is_featured=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)
        self.buyer = User.objects.create_user(
            username='buyer_pcard',
            email='buyer_pcard@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_guest_can_open_public_product_detail(self):
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unified Widget')
        self.assertFalse(response.context['show_cart_actions'])

    def test_home_uses_unified_public_card(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ver detalles')
        self.assertContains(response, 'tf-pcard')
        self.assertNotContains(response, 'picsum.photos')

    def test_buyer_product_detail_has_cart_actions(self):
        self.client.force_login(self.buyer)
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])
        self.assertContains(response, 'Add to cart')
