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
        # English seller portal copy
        self.assertContains(r, 'Talk to your data')
        self.assertContains(r, 'Revenue')
        self.assertContains(r, 'Forecasts')
        # With a single order there isn't enough history for proj tables
        self.assertContains(r, 'Forecasts need a date column')

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
            data=json.dumps({'message': 'top 5 products by sales', 'history': []}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get('table') or payload.get('text') or payload.get('fig'))
        if payload.get('table'):
            self.assertIn('tf-table', payload['table'])
            self.assertIn('Widget', payload['table'])
            self.assertIn('Product', payload['table'])

    def test_truncation_banner_when_over_limit(self):
        from unittest import mock
        from analytics import data_source as ds

        self.client.login(username='ai_seller', password='TestPass123!')
        fake_df = ds.load_company_sales_df(self.company.id)
        with mock.patch.object(ds, 'company_sales_row_count', return_value=ds.COMPANY_SALES_LIMIT + 50), \
             mock.patch.object(ds, 'load_company_sales_df', return_value=fake_df):
            r = self.client.get(reverse('analytics:seller_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Showing the newest')
        self.assertContains(r, str(ds.COMPANY_SALES_LIMIT))


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


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False, LLM_OFFLINE='1')
class TestSellerForecastAndGrowth(TestCase):
    """End-to-end checks for projections / growth / rising+falling products.

    Uses enough dated order history that the DataFlow forecasting engine
    (linear forecast + item trends) can run — a single order is not enough.
    """

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone

        ensure_default_plans()
        self.company = Company.objects.create(name='Forecast Co', ruc='FC-1', is_verified=True)
        self.seller = User.objects.create_user(
            username='fc_seller', email='fc@seller.pa', password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company.owner = self.seller
        self.company.save(update_fields=['owner'])
        start_seller_trial(self.company)

        self.buyer = User.objects.create_user(
            username='fc_buyer', email='fc@buyer.pa', password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

        cat = Category.objects.create(name='Forecast Cat')
        self.rising = Product.objects.create(
            company=self.company, category=cat, name='RisingWidget', sku='RW-1',
            unit_price=10, is_active=True,
        )
        self.falling = Product.objects.create(
            company=self.company, category=cat, name='FallingGadget', sku='FG-1',
            unit_price=20, is_active=True,
        )

        # 8 months of history so auto_freq lands on months (span > 210 days)
        base = timezone.now() - timedelta(days=240)
        for i in range(8):
            when = base + timedelta(days=30 * i)
            order = Order.objects.create(
                buyer=self.buyer, status='paid', total=0, subtotal=0,
                seller_confirmation_status='accepted', confirming_company=self.company,
            )
            Order.objects.filter(pk=order.pk).update(created_at=when)
            # Rising product: growing qty
            OrderItem.objects.create(
                order=order, product=self.rising, qty=2 + i,
                unit_price_snapshot=10,
            )
            # Falling product: shrinking qty
            OrderItem.objects.create(
                order=order, product=self.falling, qty=max(1, 12 - i),
                unit_price_snapshot=20,
            )

    def test_horizon_english_tokens(self):
        from analytics.engine.forecasting import parse_horizon

        self.assertEqual(parse_horizon('next 6 months'), ('M', 6))
        self.assertEqual(parse_horizon('growth next quarter'), ('M', 3))
        self.assertEqual(parse_horizon('next 2 weeks'), ('W', 2))
        self.assertEqual(parse_horizon('proximos 3 meses'), ('M', 3))

    def test_linear_forecast_and_item_trends_engine(self):
        from analytics import data_source as ds
        from analytics.engine import data_loader, forecasting as F

        df = data_loader.clean(ds.load_company_sales_df(self.company.id))
        date_col = F.find_date_column(df)
        self.assertEqual(date_col, 'fecha')
        freq = F.auto_freq(df, date_col)
        ts = F.build_series(df, date_col, 'line_total', freq=freq)
        self.assertIsNotNone(ts)
        result = F.linear_forecast(ts, F.default_horizon(freq))
        self.assertIsNotNone(result)
        self.assertIn('proj_growth_pct', result)
        self.assertIn('cagr', result)
        self.assertIn('forecast', result)
        self.assertGreaterEqual(len(result['forecast']), 1)

        trends = F.item_trends(df, 'producto', date_col, 'line_total', freq=freq)
        self.assertIsNotNone(trends)
        self.assertFalse(trends.empty)
        names = set(trends['producto'])
        self.assertIn('RisingWidget', names)
        self.assertIn('FallingGadget', names)

    def test_seller_dashboard_shows_forecast_section(self):
        self.client.login(username='fc_seller', password='TestPass123!')
        r = self.client.get(reverse('analytics:seller_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Forecast')
        # Should NOT show the thin-history empty state once we have months of data
        self.assertNotContains(r, 'Forecasts need a date column')
        # Rising / falling projection cards appear when change % is large enough
        body = r.content.decode()
        self.assertTrue(
            'Rising products' in body or 'Falling products' in body
            or 'Forecast ·' in body or 'an-metric-list' in body
            or 'an-forecast-block' in body,
            msg='Expected forecast charts/tables block in the HTML',
        )
        self.assertContains(r, 'an-forecast-block')
        self.assertContains(r, 'an-data-table')

    def test_chat_forecast_and_declining_products(self):
        self.client.login(username='fc_seller', password='TestPass123!')
        self.assertEqual(self.client.get(reverse('analytics:seller_dashboard')).status_code, 200)

        r = self.client.post(
            reverse('analytics:chat'),
            data=json.dumps({'message': 'forecast sales next quarter', 'history': []}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get('fig'), msg=f'Expected forecast chart, got {payload.get("text")}')
        text = (payload.get('text') or '').lower()
        self.assertTrue(
            'forecast' in text or 'growth' in text or 'cagr' in text,
            msg=f'Expected growth/forecast prose, got: {payload.get("text")}',
        )

        r2 = self.client.post(
            reverse('analytics:chat'),
            data=json.dumps({'message': 'which products are declining?', 'history': []}),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 200)
        p2 = r2.json()
        self.assertTrue(p2.get('fig') or p2.get('text'))
        blob = ((p2.get('text') or '') + (p2.get('table') or '')).lower()
        self.assertIn('fallinggadget', blob)
