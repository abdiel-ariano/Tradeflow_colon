"""Access + table-chat wiring for seller Analytics IA."""
from __future__ import annotations

import json

import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Order,
    OrderItem,
    Product,
    UserProfile,
)
from core.utils.saas_billing import ensure_default_plans
from core.utils.seller_lifecycle import start_seller_trial


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False)
class TestSellerAnalyticsAccess(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.company = Company.objects.create(name='AI Co', ruc='AI-1', is_verified=True)
        self.seller = User.objects.create_user(
            username='ai_seller', email='ai@seller.pa', password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company.owner = self.seller
        self.company.save(update_fields=['owner'])
        start_seller_trial(self.company)

        self.buyer = User.objects.create_user(
            username='ai_buyer', email='ai@buyer.pa', password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

        cat = Category.objects.create(name='Electronics AI')
        self.product = Product.objects.create(
            company=self.company, category=cat, name='Widget', sku='W-1',
            unit_price=10, is_active=True,
        )
        order = Order.objects.create(
            buyer=self.buyer, status='paid', total=20, subtotal=20,
            seller_confirmation_status='accepted', confirming_company=self.company,
        )
        OrderItem.objects.create(
            order=order, product=self.product, qty=2, unit_price_snapshot=10,
        )

    def test_seller_dashboard_renders_and_hides_arbitrary_sources(self):
        self.client.login(username='ai_seller', password='TestPass123!')
        r = self.client.get(reverse('analytics:seller_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'an-chat-input')
        # Seller embedded: no multi-source tabs/panels
        self.assertNotContains(r, 'data-panel="file"')
        self.assertNotContains(r, 'data-panel="db"')
        self.assertNotContains(r, 'name="model"')
        # CSP production: inline assets must carry the request nonce
        self.assertContains(r, 'nonce="')
        self.assertContains(r, 'an-chat-input')

    def test_buyer_cannot_open_seller_analytics(self):
        self.client.login(username='ai_buyer', password='TestPass123!')
        r = self.client.get(reverse('analytics:seller_dashboard'))
        self.assertEqual(r.status_code, 302)

    def test_non_staff_redirected_from_admin_dashboard(self):
        self.client.login(username='ai_seller', password='TestPass123!')
        r = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('analytics:seller_dashboard'))

    def test_chat_returns_custom_table_for_top_request(self):
        self.client.login(username='ai_seller', password='TestPass123!')
        # Warm cache/session via dashboard
        self.assertEqual(self.client.get(reverse('analytics:seller_dashboard')).status_code, 200)
        r = self.client.post(
            reverse('analytics:chat'),
            data=json.dumps({'message': 'top 5 por producto', 'history': []}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get('table') or payload.get('text') or payload.get('fig'))
        if payload.get('table'):
            self.assertIn('tf-table', payload['table'])
            self.assertIn('Widget', payload['table'])


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False, LLM_OFFLINE='1')
class TestAnalyticsTableEngine(TestCase):
    def test_fast_path_groupby_table(self):
        from analytics.engine import ai_analyzer

        df = pd.DataFrame({
            'producto': ['A', 'A', 'B'],
            'line_total': [10, 20, 5],
            'qty': [1, 2, 1],
        })
        text, fig, table = ai_analyzer.chat(df, [], 'tabla top productos por line_total', api_key='')
        self.assertIsNotNone(table)
        self.assertFalse(table.empty)
