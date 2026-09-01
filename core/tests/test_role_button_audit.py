"""Cross-role smoke audit for primary pages and button endpoints."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class RoleButtonAuditTests(TestCase):
    """GET/POST smoke checks for guest, buyer, seller, and admin flows."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name='Audit Supplier Co',
            legal_name='Audit Supplier Co, S.A.',
            ruc='8-AUDIT-01',
            dv='12',
            business_email='audit@supplier.pa',
            verification_document='companies/verification/audit.pdf',
            verification_status='verified',
        )
        cls.category = Category.objects.create(name='Audit Category')
        cls.product = Product.objects.create(
            company=cls.company,
            category=cls.category,
            name='Audit Widget',
            description='Audit product for button checks.',
            sku='AUD-001',
            unit_price='25.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=cls.product, stock_qty=50, reserved_qty=0)

        cls.buyer = User.objects.create_user('audit_buyer', password='Audit1234!', email='buyer@audit.pa')
        UserProfile.objects.create(user=cls.buyer, role='buyer', email_verificado=True)

        cls.seller = User.objects.create_user('audit_seller', password='Audit1234!', email='seller@audit.pa')
        UserProfile.objects.create(user=cls.seller, role='seller', email_verificado=True)
        cls.company.owner = cls.seller
        cls.company.save(update_fields=['owner'])

        cls.admin = User.objects.create_user(
            'audit_admin', password='Audit1234!', email='admin@audit.pa', is_staff=True,
        )
        UserProfile.objects.create(user=cls.admin, role='admin', email_verificado=True)

    def _assert_get_ok(self, client, role, name, *args, **kwargs):
        try:
            url = reverse(name, args=args, kwargs=kwargs)
        except NoReverseMatch:
            self.fail(f'{role}: unresolved route {name}')
        response = client.get(url)
        self.assertLess(
            response.status_code,
            500,
            msg=f'{role} GET {name} ({url}) returned {response.status_code}',
        )
        return response

    def _assert_post_ok(self, client, role, name, data=None, *args, **kwargs):
        try:
            url = reverse(name, args=args, kwargs=kwargs)
        except NoReverseMatch:
            self.fail(f'{role}: unresolved route {name}')
        response = client.post(url, data or {})
        self.assertIn(
            response.status_code,
            (200, 302, 400, 403, 404),
            msg=f'{role} POST {name} ({url}) returned {response.status_code}',
        )
        return response

    def test_guest_primary_pages_and_cart_button(self):
        client = Client()
        for name in (
            'home', 'catalogo_publico', 'login', 'signup_buyer', 'signup_seller',
            'ver_carrito', 'mapa_zlc', 'acerca_tradeflow', 'legal_terminos',
            'marketplace_deals', 'password_reset',
        ):
            self._assert_get_ok(client, 'guest', name)
        self._assert_get_ok(client, 'guest', 'catalogo_producto_detail', pk=self.product.pk)
        self._assert_post_ok(
            client, 'guest', 'agregar_al_carrito', {'cantidad': 1}, producto_id=self.product.pk,
        )

    def test_buyer_primary_pages_and_logout_button(self):
        client = Client()
        client.force_login(self.buyer)
        for name in (
            'mi_perfil', 'mis_ordenes', 'mis_cotizaciones', 'checkout',
            'catalogo_publico', 'ver_carrito',
        ):
            self._assert_get_ok(client, 'buyer', name)
        self._assert_post_ok(
            client, 'buyer', 'agregar_al_carrito', {'cantidad': 1}, producto_id=self.product.pk,
        )
        self._assert_post_ok(client, 'buyer', 'logout')

    def test_seller_primary_pages_and_logout_button(self):
        client = Client()
        client.force_login(self.seller)
        for name in (
            'portal_seller', 'seller_mis_productos', 'seller_agregar_producto',
            'seller_mis_ventas', 'seller_plan_consumo', 'mi_perfil',
            'seller_company_qr', 'seller_predictive_insights', 'seller_balances',
            'seller_customers', 'seller_tax', 'seller_data_management',
            'seller_disputes', 'seller_apps', 'seller_setup_guide',
            'seller_global_search', 'seller_reporting', 'seller_cotizaciones',
            'seller_dashboard', 'catalogo_publico',
        ):
            self._assert_get_ok(client, 'seller', name)
        self._assert_post_ok(client, 'seller', 'logout')

    def test_admin_primary_pages_and_logout_button(self):
        client = Client()
        client.force_login(self.admin)
        for name in (
            'dashboard', 'admin_saas_dashboard', 'lista_productos', 'catalogo_publico',
            'lista_ordenes', 'lista_empresas', 'admin_applications', 'admin_panel_search',
            'nueva_orden_paso1',
        ):
            self._assert_get_ok(client, 'admin', name)
        self._assert_post_ok(client, 'admin', 'logout')

    def test_guest_marketplace_and_legal_buttons(self):
        client = Client()
        for name in (
            'marketplace_verified_suppliers', 'marketplace_order_protection',
            'legal_privacidad', 'legal_cookies', 'solicitud_acceso',
        ):
            self._assert_get_ok(client, 'guest', name)

    def test_buyer_quote_and_cart_buttons(self):
        client = Client()
        client.force_login(self.buyer)
        self._assert_post_ok(
            client, 'buyer', 'catalogo_agregar_inquiry', {'cantidad': 1}, producto_id=self.product.pk,
        )
        self._assert_post_ok(
            client, 'buyer', 'solicitar_cotizacion_automatica', {'cantidad': 1}, producto_id=self.product.pk,
        )
        self._assert_get_ok(client, 'buyer', 'solicitar_cotizacion')

    def test_language_switcher_post_for_guest_and_buyer(self):
        for user_label, user in (('guest', None), ('buyer', self.buyer)):
            client = Client()
            if user:
                client.force_login(user)
            response = client.post('/i18n/setlang/', {'language': 'es', 'next': '/'})
            self.assertIn(response.status_code, (200, 302), msg=f'{user_label} language switch failed')
