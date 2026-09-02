"""USD money formatting and dashboard chart numeric precision.

Seller analytics and admin KPIs must show two-decimal USD without
double prefixes or float noise from Decimal conversions.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import UserProfile
from core.utils.money_format import format_money_usd, money_to_chart_float, quantize_money


class MoneyFormatTests(TestCase):
    """Assert format_money_usd and quantize helpers."""

    def test_format_usd_positive(self):
        """Format positive amounts with USD prefix and thousands."""
        self.assertEqual(format_money_usd(Decimal('658238.34')), 'USD 658,238.34')

    def test_format_usd_no_double_prefix(self):
        """Avoid repeating the USD label in formatted output."""
        s = format_money_usd(Decimal('10'))
        self.assertEqual(s.count('USD'), 1)
        self.assertFalse(s.startswith('USD USD'))

    def test_quantize_two_decimals(self):
        """Round monetary values to exactly two decimal places."""
        self.assertEqual(quantize_money(Decimal('1.999')), Decimal('2.00'))
        self.assertEqual(quantize_money('658238.3400000000'), Decimal('658238.34'))

    def test_chart_float_max_two_decimals(self):
        """Convert Decimal to chart float with at most two decimals."""
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
    """Assert admin dashboard API income series stay two decimals."""

    def setUp(self):
        """Log in a TradeFlow admin for dashboard-stats API calls."""
        self.admin = User.objects.create_user(
            username='admin_money',
            email='admin@money.pa',
            password='AdminPass123!',
        )
        UserProfile.objects.create(user=self.admin, role='admin', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.admin)

    def test_api_dashboard_ingresos_two_decimal_places(self):
        """Keep ingresos_por_dia values within two fractional digits."""
        resp = self.client.get('/api/dashboard-stats/?dias=7')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for val in data.get('ingresos_por_dia', []):
            dec_part = f'{val:.10f}'.split('.')[-1].rstrip('0')
            if dec_part:
                self.assertLessEqual(len(dec_part), 2)
