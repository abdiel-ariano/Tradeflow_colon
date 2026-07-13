"""Order protection landing — distinct export-bond UI for guests."""
from django.test import TestCase, override_settings


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class MarketplaceOrderProtectionPageTests(TestCase):
    def test_guest_sees_protection_bond_ui(self):
        response = self.client.get('/order-protection/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'op-hero')
        self.assertContains(response, 'TradeFlow')
        self.assertContains(response, 'Quote first')
        self.assertContains(response, 'op-bond')
        self.assertContains(response, 'op-rail')
        self.assertContains(response, 'op-ledger')
        self.assertContains(response, 'marketplace-protection.css')
        self.assertNotContains(response, 'mkt-hero--protection')
        self.assertNotContains(response, '🛡️')
