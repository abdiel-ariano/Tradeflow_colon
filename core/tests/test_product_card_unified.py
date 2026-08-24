"""Unified product cards and public PDP for CFZ catalog.

Guests see wholesale teasers without cart actions; verified
buyers get cart/quote controls on the same detail template.
"""
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
    """Assert PDP and home card markup for guests and buyers."""

    def setUp(self):
        """Seed featured products, related SKU, and verified buyer."""
        from django.core.cache import cache
        cache.clear()
        self.company = Company.objects.create(
            name='CFZ Demo Co',
            is_verified=True,
            ruc='123456789',
        )
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Unified Widget',
            description='A reliable widget for export.',
            sku='UW-001',
            unit_price='99.99',
            currency='USD',
            is_active=True,
            is_featured=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)
        for i in range(2, 8):
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Featured Widget {i}',
                sku=f'UW-{i:03d}',
                unit_price='49.99',
                currency='USD',
                is_active=True,
                is_featured=True,
            )
        self.related = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Related Gadget',
            sku='RG-002',
            unit_price='49.99',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.related, stock_qty=5, reserved_qty=0)
        self.buyer = User.objects.create_user(
            username='buyer_pcard',
            email='buyer_pcard@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_guest_can_open_public_product_detail(self):
        """Open PDP publicly with teaser pricing and related SKUs."""
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unified Widget')
        self.assertContains(response, 'From')
        self.assertContains(response, 'Sign up to view wholesale pricing')
        self.assertContains(response, 'CFZ Verified')
        self.assertContains(response, 'Export Ready')
        self.assertFalse(response.context['show_cart_actions'])
        self.assertContains(response, 'og:title')
        self.assertContains(response, 'Related products')

    def test_guest_breadcrumb_shows_category(self):
        """Show Home and category crumbs on guest PDP."""
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertContains(response, 'Home')
        self.assertContains(response, 'Electronics')

    def test_home_uses_catalog_marketplace_cards(self):
        """Render marketplace product-card markup on home."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hm-alibaba')
        self.assertContains(response, 'product-card')
        self.assertContains(response, 'btn-inquiry')
        self.assertContains(response, 'Add to inquiry')
        self.assertContains(response, 'CFZ Verified')
        self.assertNotContains(response, 'class="tf-pcard ')

    def test_buyer_product_detail_has_cart_actions(self):
        """Show cart and auto-quote actions for logged-in buyers."""
        self.client.force_login(self.buyer)
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])
        self.assertContains(response, 'Add to inquiry')
        self.assertNotContains(response, 'Add to cart')
        self.assertContains(response, 'Auto quote')
        self.assertNotContains(response, 'Regístrate para ver precios mayoristas')
