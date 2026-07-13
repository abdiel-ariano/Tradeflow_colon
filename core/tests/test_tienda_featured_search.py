"""Tienda (/tienda/) — misma UI del catálogo público con filtros AJAX."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class TiendaFeaturedSearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='buyer_feat',
            email='feat@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=True,
        )
        self.company = Company.objects.create(name='CFZ Featured Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        for i in range(5):
            product = Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Widget {i}',
                sku=f'W-{i}',
                unit_price='10.00',
                currency='USD',
                is_active=True,
            )
            Inventory.objects.create(product=product, stock_qty=50)
        self.client.force_login(self.user)

    def test_empresa_filter_shows_supplier_products(self):
        resp = self.client.get(f'/tienda/?empresa={self.company.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CFZ Featured Co')
        self.assertContains(resp, 'Widget 0')
        self.assertEqual(resp.context['catalog_url_name'], 'tienda')

    def test_categoria_filter_shows_catalog_cards(self):
        resp = self.client.get(f'/tienda/?categoria={self.category.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'cat-filters-toolbar')
        self.assertContains(resp, 'tf-pcard')
        self.assertContains(resp, 'Electronics')
        self.assertContains(resp, 'MOQ')
        self.assertContains(resp, 'CFZ Verified')

    def test_partial_ajax_returns_results_grid(self):
        resp = self.client.get(
            f'/tienda/?empresa={self.company.pk}&partial=1',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="cat-results-root"')

    def test_product_cards_use_catalog_seed_in_img_src(self):
        resp = self.client.get('/tienda/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('src="/static/images/catalog-seeds/', html)
        self.assertNotIn('src="/static/images/category-icons/', html)
