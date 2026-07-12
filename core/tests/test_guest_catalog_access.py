"""Catálogo público: invitados pueden explorar sin login."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class GuestCatalogAccessTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.buyer = User.objects.create_user(
            username='buyer_guest_test',
            email='buyer_guest@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_guest_can_open_tienda(self):
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'td-product-grid', status_code=200)

    def test_guest_tienda_has_cart_actions(self):
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])
        self.assertTrue(response.context['is_guest_catalog'])

    def test_guest_can_add_to_cart(self):
        from core.models import Product, Company, Category, Inventory

        company = Company.objects.create(name='Guest Co', is_verified=True)
        cat = Category.objects.create(name='Cat')
        product = Product.objects.create(
            name='Guest Product',
            sku='GUEST-1',
            company=company,
            category=cat,
            unit_price='10.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=product, stock_qty=50, reserved_qty=0)
        resp = self.client.post(
            reverse('agregar_al_carrito', kwargs={'producto_id': product.pk}),
            {'cantidad': 1},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('carrito', self.client.session)

    def test_guest_home_links_to_tienda_not_login_wall(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('catalogo_publico'))
        self.assertNotContains(response, 'login/?next=/tienda/')

    def test_unverified_buyer_can_browse_tienda(self):
        unverified = User.objects.create_user(
            username='unverified_buyer',
            email='unverified@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=unverified, role='buyer', email_verificado=False)
        self.client.force_login(unverified)
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])

    def test_buyer_still_has_cart_actions(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])

    def test_guest_verificado_filter(self):
        response = self.client.get('/tienda/', {'verificado': '1'})
        self.assertEqual(response.status_code, 200)

    def test_authenticated_buyer_catalog_shows_marketplace_nav(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cat-catalog-nav"')
        self.assertContains(response, 'Verified suppliers')

    def test_authenticated_buyer_catalog_has_cart_form(self):
        from core.models import Product, Company, Category, Inventory

        company = Company.objects.create(name='Catalog Co', is_verified=True)
        cat = Category.objects.create(name='Electronics')
        product = Product.objects.create(
            name='Catalog Product',
            sku='CAT-1',
            company=company,
            category=cat,
            unit_price='15.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=product, stock_qty=25, reserved_qty=0)

        self.client.force_login(self.buyer)
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])
        self.assertContains(response, 'js-cart-add-form')

    def test_catalog_inquiry_ajax_returns_json(self):
        from core.models import Product, Company, Category, Inventory

        company = Company.objects.create(name='Ajax Co', is_verified=True)
        cat = Category.objects.create(name='Electronics')
        product = Product.objects.create(
            name='Ajax Product',
            sku='AJAX-1',
            company=company,
            category=cat,
            unit_price='12.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=product, stock_qty=20, reserved_qty=0)
        response = self.client.post(
            reverse('catalogo_agregar_inquiry', kwargs={'producto_id': product.pk}),
            {'cantidad': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn('carrito', self.client.session)
