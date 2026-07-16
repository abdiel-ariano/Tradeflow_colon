"""Public catalog filters by empresa/categoria and seed images.

Buyers narrow CFZ inventory without legacy Ali-style cards;
partial /tienda/ URLs still redirect into /catalogo/.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class TiendaFeaturedSearchTests(TestCase):
    """Assert catalog filters, cards, and seed image srcs."""

    def setUp(self):
        """Seed verified company products and log in a buyer."""
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

    def test_empresa_filter_shows_company_products(self):
        """Filter catalog results to the selected company."""
        resp = self.client.get(f'{reverse("catalogo_publico")}?empresa={self.company.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CFZ Featured Co')
        self.assertContains(resp, 'Widget 0')

    def test_categoria_filter_shows_compact_catalog_cards(self):
        """Show compact product-card markup for category filters."""
        resp = self.client.get(f'{reverse("catalogo_publico")}?categoria={self.category.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'product-card')
        self.assertContains(resp, 'Electronics')
        self.assertContains(resp, 'MOQ')
        self.assertContains(resp, 'CFZ Verified')
        self.assertNotContains(resp, 'ali-product-card')
        self.assertNotContains(resp, 'Chatea ahora')

    def test_tienda_partial_redirects_to_catalog(self):
        """301 legacy tienda partials onto catalogo with filters."""
        resp = self.client.get(
            f'/tienda/?empresa={self.company.pk}&partial=1',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            follow=False,
        )
        self.assertEqual(resp.status_code, 301)
        self.assertIn('/catalogo/', resp['Location'])
        self.assertIn('partial=1', resp['Location'])

    def test_product_cards_use_catalog_seed_in_img_src(self):
        """Use catalog-seeds images instead of category icons."""
        resp = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('src="/static/images/catalog-seeds/', html)
        self.assertNotIn('src="/static/images/category-icons/', html)
