"""
Tests de formateo monetario y payload del dashboard API.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import UserProfile
from core.utils.money_format import format_money_usd, money_to_chart_float, quantize_money


class MoneyFormatTests(TestCase):
    def test_format_usd_positive(self):
        """Test format usd positive."""
        self.assertEqual(format_money_usd(Decimal('658238.34')), 'USD 658,238.34')

    def test_format_usd_no_double_prefix(self):
        """Test format usd no double prefix."""
        s = format_money_usd(Decimal('10'))
        self.assertEqual(s.count('USD'), 1)
        self.assertFalse(s.startswith('USD USD'))

    def test_quantize_two_decimals(self):
        """Test quantize two decimals."""
        self.assertEqual(quantize_money(Decimal('1.999')), Decimal('2.00'))
        self.assertEqual(quantize_money('658238.3400000000'), Decimal('658238.34'))

    def test_chart_float_max_two_decimals(self):
        """Test chart float max two decimals."""
        f = money_to_chart_float(Decimal('10.999'))
        self.assertEqual(f, 11.0)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class DashboardStatsApiMoneyTests(TestCase):
    def setUp(self):
        """Setup."""
        self.admin = User.objects.create_user(
            username='admin_money',
            email='admin@money.pa',
            password='AdminPass123!',
        )
        UserProfile.objects.create(user=self.admin, role='admin', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.admin)

    def test_api_dashboard_ingresos_two_decimal_places(self):
        """Test api dashboard ingresos two decimal places."""
        resp = self.client.get('/api/dashboard-stats/?dias=7')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for val in data.get('ingresos_por_dia', []):
            dec_part = f'{val:.10f}'.split('.')[-1].rstrip('0')
            if dec_part:
                self.assertLessEqual(len(dec_part), 2)
