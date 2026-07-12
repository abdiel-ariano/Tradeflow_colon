"""Public catalog — product cards and seed images."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

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
        """Setup."""
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

    def test_tienda_redirects_to_catalog(self):
        """Test tienda redirects to catalog."""
        self.client.login(username='store_buyer', password='TestPass123!')
        response = self.client.get('/tienda/', follow=False)
        self.assertEqual(response.status_code, 301)
        self.assertIn('/catalogo/', response['Location'])

    def test_catalog_shows_product_cards(self):
        """Test catalog shows product cards."""
        self.client.login(username='store_buyer', password='TestPass123!')
        response = self.client.get(reverse('catalogo_publico'))
        html = response.content.decode()
        self.assertIn('product-card', html)
        self.assertNotIn('picsum.photos', html)
