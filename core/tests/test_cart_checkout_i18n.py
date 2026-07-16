"""Cart and checkout copy under English and Spanish locales.

Wholesale buyers switching language mid-session must see matching cart
CTA copy so checkout feels native for CFZ and LatAm traffic.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Inventory,
    Product,
    UserProfile,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    AXES_ENABLED=False,
    LANGUAGE_CODE='en',
)
class CartCheckoutI18nTests(TestCase):
    """Assert cart strings and the buyer navbar language switcher."""

    def setUp(self):
        """Log in a buyer with one in-stock line already in session cart."""
        company = Company.objects.create(name='Co', ruc='1', is_verified=True)
        cat = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            company=company,
            category=cat,
            name='Widget',
            sku='W-I18N',
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)
        self.user = User.objects.create_user(
            username='i18n_buyer',
            email='i18n@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['carrito'] = {
            str(self.product.pk): {
                'nombre': self.product.name,
                'precio': str(self.product.unit_price),
                'cantidad': 1,
                'subtotal': str(self.product.unit_price),
                'imagen': '',
            }
        }
        session.save()

    def test_cart_renders_english_when_en_active(self):
        """English locale shows Shopping cart / Proceed to checkout copy."""
        resp = self.client.get(reverse('ver_carrito'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Shopping cart')
        self.assertContains(resp, 'Proceed to checkout')
        self.assertNotContains(resp, 'Carrito de compras')

    def test_buyer_navbar_has_language_switcher(self):
        """Buyer navbar exposes the setlang language switcher controls."""
        resp = self.client.get(reverse('ver_carrito'))
        self.assertContains(resp, 'bn-lang-link')
        self.assertContains(resp, 'i18n/setlang')

    def test_cart_renders_spanish_under_es_prefix(self):
        """After switching to es, cart shows Spanish checkout CTAs."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('ver_carrito')},
        )
        resp = self.client.get(post_response.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Carrito de compras')
        self.assertContains(resp, 'Finalizar compra')
        self.assertNotContains(resp, 'Shopping cart')
