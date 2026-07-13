"""Catálogo público /catalogo/ — read-only sin login."""
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
class CatalogoPublicoTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='CFZ Wholesale', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Wholesale Gadget',
            sku='WG-100',
            unit_price='150.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=20, reserved_qty=0)

    def test_guest_can_browse_catalogo(self):
        response = self.client.get('/catalogo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Colón Free Zone Catalog')
        self.assertContains(response, 'Wholesale Gadget')
        self.assertContains(response, 'tf-pcard')
        self.assertContains(response, 'Colón Free Zone Wholesale Catalog')
        self.assertNotContains(response, 'cat-sort-select--quick')
        self.assertContains(response, 'Verificado')

    def test_search_filter(self):
        response = self.client.get('/catalogo/', {'buscar': 'Wholesale'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wholesale Gadget')
        self.assertEqual(response.context['total_resultados'], 1)

    def test_empty_state_suggestions(self):
        response = self.client.get('/catalogo/', {'buscar': 'zzznomatch'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No products found')
        self.assertContains(response, 'Electronics')

    def test_partial_returns_grid_only(self):
        response = self.client.get('/catalogo/', {'partial': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cat-product-grid')
        self.assertNotContains(response, '<!DOCTYPE html>')

    def test_home_links_to_catalogo(self):
        Product.objects.filter(pk=self.product.pk).update(is_featured=True)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/catalogo/')

    def test_buyer_can_browse_without_redirect(self):
        buyer = User.objects.create_user('buyer_cat', 'buyer_cat@test.pa', 'Test1234!')
        UserProfile.objects.create(user=buyer, role='buyer', email_verificado=True)
        self.client.force_login(buyer)
        response = self.client.get('/catalogo/')
        self.assertEqual(response.status_code, 200)
