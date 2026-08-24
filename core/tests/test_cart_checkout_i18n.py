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
    """Assert RFQ strings and the buyer navbar language switcher."""

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
        """English locale presents an RFQ instead of consumer checkout."""
        resp = self.client.get(reverse('ver_carrito'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Request for Quotation')
        self.assertContains(resp, 'Quote before you commit')
        self.assertContains(resp, 'Request for Quotation before payment')
        self.assertNotContains(resp, 'Shopping cart')
        self.assertNotContains(resp, 'Proceed to checkout')
        self.assertNotContains(resp, 'Payment methods')
        self.assertNotContains(resp, 'Tax (16% VAT)')

    def test_global_footer_rejects_unsupported_b2c_guarantees(self):
        """The shared footer advertises RFQs, not payment or delivery guarantees."""
        resp = self.client.get(reverse('ver_carrito'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(
            resp,
            'Every wholesale path on TradeFlow stays quote-first',
        )
        for unsupported in (
            'Buyer Protection',
            'Secure payments',
            'Money-back guarantee',
            'Guaranteed delivery',
            'We accept:',
            'Visa',
            'PayPal',
        ):
            self.assertNotContains(resp, unsupported)

        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('ver_carrito')},
        )
        resp_es = self.client.get(post_response.url)
        self.assertContains(
            resp_es,
            'Cada compra mayorista en TradeFlow empieza con cotización',
        )
        for unsupported in (
            'Protección al comprador',
            'Pagos seguros',
            'Garantía de devolución',
            'Entrega garantizada',
            'Aceptamos:',
        ):
            self.assertNotContains(resp_es, unsupported)

    def test_buyer_navbar_has_language_switcher(self):
        """Buyer navbar exposes the setlang language switcher controls."""
        resp = self.client.get(reverse('ver_carrito'))
        self.assertContains(resp, 'bn-lang-link')
        self.assertContains(resp, 'i18n/setlang')

    def test_cart_renders_spanish_under_es_prefix(self):
        """Spanish locale keeps the same quote-first commercial flow."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('ver_carrito')},
        )
        resp = self.client.get(post_response.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Solicitud de cotización')
        self.assertContains(resp, 'Cotiza antes de comprar')
        self.assertContains(resp, 'Solicitud de cotización antes del pago')
        self.assertNotContains(resp, 'Carrito de compras')
        self.assertNotContains(resp, 'Finalizar compra')
        self.assertNotContains(resp, 'Métodos de pago')
