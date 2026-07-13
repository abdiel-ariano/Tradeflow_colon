"""Buyer store (/tienda/) — misma landing de catálogo público."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Category, Company, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class BuyerStoreLandingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ZLC Trading', is_verified=True)
        self.electronics = Category.objects.create(name='Electronics & Office')
        self.gaming = Category.objects.create(name='Gaming & Peripherals')
        for i in range(6):
            Product.objects.create(
                company=self.company,
                category=self.electronics if i < 4 else self.gaming,
                name=f'Widget {i}',
                sku=f'W-{i:02d}',
                unit_price=Decimal('25.00'),
                currency='USD',
                is_active=True,
                is_featured=True,
                merchandising_priority=20 - i,
            )
        self.buyer = User.objects.create_user(
            username='store_buyer',
            email='store@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_tienda_renders_public_catalog_template(self):
        self.client.login(username='store_buyer', password='TestPass123!')
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cat-filters-toolbar')
        self.assertEqual(response.context['catalog_url_name'], 'tienda')
        self.assertGreaterEqual(response.context['total_resultados'], 2)

    def test_tienda_shows_product_names_in_grid(self):
        self.client.login(username='store_buyer', password='TestPass123!')
        response = self.client.get('/tienda/')
        html = response.content.decode()
        self.assertIn('Widget 0', html)
        self.assertIn('tf-pcard', html)
        self.assertNotIn('picsum.photos', html)
