"""Catálogo seller: solo activos por defecto y toggle actualiza KPIs."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Category, Company, Product, UserProfile


class SellerProductsActiveFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user(
            username='seller_prod',
            email='seller_prod@test.pa',
            password='test-pass-123',
        )
        UserProfile.objects.create(
            user=self.seller,
            role='seller',
            email_verificado=True,
        )
        self.company = Company.objects.create(
            name='Test Co',
            ruc='8-888-888',
            owner=self.seller,
        )
        cat = Category.objects.create(name='Cat A')
        Product.objects.create(
            company=self.company,
            category=cat,
            name='Active One',
            unit_price='10.00',
            is_active=True,
        )
        Product.objects.create(
            company=self.company,
            category=cat,
            name='Active Two',
            unit_price='12.00',
            is_active=True,
        )
        Product.objects.create(
            company=self.company,
            category=cat,
            name='Inactive One',
            unit_price='8.00',
            is_active=False,
        )
        self.client.force_login(self.seller)

    def test_default_list_shows_only_active_products(self):
        resp = self.client.get(reverse('seller_mis_productos'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Active One')
        self.assertContains(resp, 'Active Two')
        self.assertNotContains(resp, 'Inactive One')

    def test_todos_filter_shows_inactive(self):
        resp = self.client.get(reverse('seller_mis_productos'), {'estado': 'todos'})
        self.assertContains(resp, 'Inactive One')

    def test_toggle_returns_updated_active_count(self):
        inactive = Product.objects.get(name='Inactive One')
        url = reverse('seller_toggle_producto', kwargs={'pk': inactive.pk})
        resp = self.client.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['is_active'])
        self.assertEqual(data['kpi_activos'], 3)
