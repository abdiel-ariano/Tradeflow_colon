"""Critical buyer purchase flow: catalog, cart, checkout, and role gates.

Covers CFZ wholesale order creation, inventory reservation, order
privacy, and post-login routing for buyers vs sellers.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    TransportCarrier,
    UserProfile,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    CHECKOUT_AUTO_APPROVE=True,
    STAFF_MFA_REQUIRED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AUTHENTICATION_BACKENDS=[
        'django.contrib.auth.backends.ModelBackend',
    ],
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class TestFlujoBuyer(TestCase):
    """End-to-end buyer marketplace path and role-based redirects."""

    def setUp(self):
        """Seed buyer, other buyer, seller, admin, product, and carrier."""
        self.company = Company.objects.create(
            name='Empresa Demo ZLC',
            ruc='123456',
            is_verified=True,
        )
        self.carrier = TransportCarrier.objects.create(
            code='test-carrier',
            name='Test Carrier',
            base_shipping_cost=Decimal('5.00'),
        )
        self.cat = Category.objects.create(name='Electrónica')
        self.product = Product.objects.create(
            company=self.company,
            category=self.cat,
            name='Producto Test',
            description='Desc',
            sku='SKU-1',
            unit_price=Decimal('10.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=50, reserved_qty=0)

        self.buyer = User.objects.create_user(
            username='buyer_test',
            email='buyer@test.pa',
            password='TestPass123!',
            first_name='Ana',
            last_name='Buyer',
        )
        UserProfile.objects.create(
            user=self.buyer,
            role='buyer',
            business_role_intent='buyer',
            phone='+507 6000-0000',
            email_verificado=True,
        )
        self.buyer_company = Company.objects.create(
            name='Compradora Demo, S.A.',
            legal_name='Compradora Demo, S.A.',
            ruc='8-COMPRA-1',
            dv='10',
            business_email=self.buyer.email,
            business_role='buyer',
            owner=self.buyer,
            is_verified=True,
            verification_status='verified',
        )

        self.other = User.objects.create_user(
            username='buyer_otro',
            email='otro@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.other, role='buyer', email_verificado=True)

        self.seller_user = User.objects.create_user(
            username='seller_test',
            email='seller@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller_user, role='seller', email_verificado=True)
        # Seller without company → wizard; with company+trial → portal (below).

        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.pa',
            password='TestPass123!',
            is_staff=True,
        )
        UserProfile.objects.create(user=self.admin_user, role='admin', email_verificado=True)

    def test_buyer_puede_ver_catalogo(self):
        """Authenticated buyer reaches /catalogo/ with HTTP 200."""
        self.client.login(username='buyer_test', password='TestPass123!')
        r = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(r.status_code, 200)

    def test_agregar_producto_al_carrito(self):
        """POST add-to-cart updates the session carrito quantity."""
        self.client.login(username='buyer_test', password='TestPass123!')
        url = f'/carrito/agregar/{self.product.pk}/'
        r = self.client.post(url, {'cantidad': 2})
        self.assertEqual(r.status_code, 302)
        session = self.client.session
        carrito = session.get('carrito', {})
        self.assertIn(str(self.product.pk), carrito)
        self.assertEqual(carrito[str(self.product.pk)]['cantidad'], 2)

    def test_checkout_crea_orden(self):
        """Checkout POST creates Order, OrderItems, and Payment rows."""
        self.client.login(username='buyer_test', password='TestPass123!')
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
        r = self.client.post(
            '/checkout/',
            {
                'notas': 'Test',
                'transport_carrier': self.carrier.pk,
                'buyer_latitude': '9.3667000',
                'buyer_longitude': '-79.9000000',
                'location_consent': '1',
            },
        )
        self.assertEqual(r.status_code, 302)
        orden = Order.objects.filter(buyer=self.buyer).first()
        self.assertIsNotNone(orden)
        self.assertEqual(orden.items.count(), 1)
        self.assertTrue(Payment.objects.filter(order=orden).exists())

    def test_checkout_reserva_inventario(self):
        """Checkout increases reserved_qty to match ordered units."""
        self.client.login(username='buyer_test', password='TestPass123!')
        session = self.client.session
        session['carrito'] = {
            str(self.product.pk): {
                'nombre': self.product.name,
                'precio': str(self.product.unit_price),
                'cantidad': 3,
                'subtotal': str(self.product.unit_price * 3),
                'imagen': '',
            }
        }
        session.save()
        self.client.post(
            '/checkout/',
            {
                'notas': '',
                'transport_carrier': self.carrier.pk,
                'buyer_latitude': '9.3667000',
                'buyer_longitude': '-79.9000000',
                'location_consent': '1',
            },
        )
        inv = Inventory.objects.get(product=self.product)
        self.assertEqual(inv.reserved_qty, 3)

    def test_buyer_ve_solo_sus_ordenes(self):
        """Buyers cannot open another buyer's order detail (404)."""
        orden_otra = Order.objects.create(
            buyer=self.other,
            shipping_cost=Decimal('0'),
            status='pending',
        )
        self.client.login(username='buyer_test', password='TestPass123!')
        r = self.client.get(f'/mis-ordenes/{orden_otra.pk}/')
        self.assertEqual(r.status_code, 404)

    def test_admin_detalle_orden_lista_todas_las_lineas(self):
        """Admin order detail lists every OrderItem line for large orders."""
        orden = Order.objects.create(
            buyer=self.buyer,
            shipping_cost=Decimal('0'),
            status='paid',
        )
        n = 5
        for _ in range(n):
            OrderItem.objects.create(
                order=orden,
                product=self.product,
                qty=1,
                unit_price_snapshot=self.product.unit_price,
            )
        orden.recalculate_totals()
        orden.save()
        self.client.login(username='admin_test', password='TestPass123!')
        r = self.client.get(f'/ordenes/{orden.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.product.name, count=n)

    def test_login_redirige_empresa_compradora_a_catalogo(self):
        """A verified buying company lands on the wholesale catalog."""
        r = self.client.post(
            '/login/',
            {'username': 'buyer_test', 'password': 'TestPass123!'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('/catalogo/', r.url)

    def test_login_redirige_seller_sin_empresa_a_wizard(self):
        """Seller without a Company.owner link goes to seller onboarding."""
        r = self.client.post(
            '/login/',
            {'username': 'seller_test', 'password': 'TestPass123!'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('/onboarding/empresa/', r.url)

    def test_login_redirige_seller_con_empresa_a_portal(self):
        """Seller with company and active trial lands on /mi-tienda/."""
        from core.utils.seller_lifecycle import start_seller_trial

        company = Company.objects.create(
            name='Seller Test Co',
            legal_name='Seller Test Co, S.A.',
            ruc='8-ST-1',
            dv='11',
            business_email=self.seller_user.email,
            business_role='seller',
            owner=self.seller_user,
            is_verified=True,
            verification_status='verified',
        )
        start_seller_trial(company)
        r = self.client.post(
            '/login/',
            {'username': 'seller_test', 'password': 'TestPass123!'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('/mi-tienda/', r.url)

    def test_home_permite_seller_sin_empresa_salir_del_wizard(self):
        """Seller without a company can open public home (escape the wizard)."""
        self.client.login(username='seller_test', password='TestPass123!')
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_checkout_spanish_ui(self):
        """Checkout renders Spanish confirm/delivery copy after setlang."""
        from django.urls import reverse

        self.client.login(username='buyer_test', password='TestPass123!')
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
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('checkout')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirmar pedido')
        self.assertContains(response, 'Ubicación de entrega')
        self.assertContains(response, 'Usar mi ubicación actual')
        self.assertContains(response, 'location_consent')
        self.assertContains(response, 'Enviar pedido')
        self.assertNotContains(response, 'Confirm order')

    def test_checkout_requiere_consentimiento_ubicacion(self):
        """Checkout without location_consent must not create an order."""
        self.client.login(username='buyer_test', password='TestPass123!')
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
        r = self.client.post(
            '/checkout/',
            {
                'notas': 'Test',
                'transport_carrier': self.carrier.pk,
                'buyer_latitude': '9.3667000',
                'buyer_longitude': '-79.9000000',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Order.objects.filter(buyer=self.buyer).exists())

    def test_acceso_sin_login_redirige(self):
        """Guests browse catalog and cart; checkout still requires login."""
        r = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['show_cart_actions'])

        r = self.client.post(f'/carrito/agregar/{self.product.pk}/', {'cantidad': 1})
        self.assertEqual(r.status_code, 302)
        self.assertIn(str(self.product.pk), self.client.session.get('carrito', {}))

        r = self.client.get('/checkout/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)
