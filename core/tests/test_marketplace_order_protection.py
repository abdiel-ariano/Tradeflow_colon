"""Order protection landing — shared marketplace shell with protection accents."""
from django.test import TestCase, override_settings


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class MarketplaceOrderProtectionPageTests(TestCase):
    def test_guest_sees_protection_page_in_marketplace_family(self):
        response = self.client.get('/order-protection/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mkt-verified-hero')
        self.assertContains(response, 'TradeFlow')
        self.assertContains(response, 'Order protection for wholesale buyers')
        self.assertContains(response, 'mkt-verified-trust')
        self.assertContains(response, 'mkt-steps--protection')
        self.assertContains(response, 'marketplace-protection.css')
        self.assertNotContains(response, 'op-hero')
        self.assertNotContains(response, 'op-bond')
        self.assertNotContains(response, '🛡️')
