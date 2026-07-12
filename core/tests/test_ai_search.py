"""Tests for AI search suggestions API."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Product, UserProfile


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False)
class TestAiSearchSuggest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Search Co', ruc='888', is_verified=True)
        self.cat = Category.objects.create(name='Electronics')
        Product.objects.create(
            company=self.company,
            name='Laptop Pro 15',
            sku='LP-15',
            category=self.cat,
            unit_price='999.00',
            currency='USD',
            is_active=True,
        )
        self.seller = User.objects.create_user(
            username='search_seller',
            email='search@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company.owner = self.seller
        self.company.save(update_fields=['owner'])

    def test_public_search_returns_products(self):
        r = self.client.get(reverse('api_search_suggest'), {'q': 'Laptop', 'scope': 'public'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertTrue(any(s['type'] == 'product' for s in data['suggestions']))

    def test_public_search_empty_query_returns_trending(self):
        r = self.client.get(reverse('api_search_suggest'), {'q': '', 'scope': 'public'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertTrue(len(data['suggestions']) > 0)

    def test_seller_search_requires_auth(self):
        r = self.client.get(reverse('api_search_suggest'), {'q': 'Laptop', 'scope': 'seller'})
        self.assertEqual(r.status_code, 401)

    def test_seller_search_finds_own_product(self):
        self.client.login(username='search_seller', password='TestPass123!')
        r = self.client.get(reverse('api_search_suggest'), {'q': 'Laptop', 'scope': 'seller'})
        self.assertEqual(r.status_code, 200)
        labels = [s['label'] for s in r.json()['suggestions']]
        self.assertIn('Laptop Pro 15', labels)

@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False)
class TestSellerExports(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Export Co', ruc='777', is_verified=True)
        self.seller = User.objects.create_user(
            username='export_seller',
            email='export@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company.owner = self.seller
        self.company.save(update_fields=['owner'])
        Product.objects.create(
            company=self.company,
            name='Export Widget',
            sku='W-1',
            unit_price='10.00',
            currency='USD',
            is_active=True,
        )

    def test_export_productos_csv(self):
        self.client.login(username='export_seller', password='TestPass123!')
        r = self.client.get(reverse('seller_export_productos_csv'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn(b'Export Widget', r.content)
