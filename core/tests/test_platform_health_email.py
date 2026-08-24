"""Platform health payload email section for ops checks.

Exposes non-secret Resend readiness and public from-address so
deploy verification can confirm mail config without secrets.
"""
from django.test import SimpleTestCase, override_settings

from core.utils.platform_health import platform_health_payload


@override_settings(
    RESEND_API_KEY='re_test',
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEFAULT_FROM_EMAIL='TradeFlow Colón <no-reply@tradeflowcolon.com>',
    DEBUG=False,
)
class PlatformHealthEmailConfigTests(SimpleTestCase):
    """Assert email block of platform_health_payload."""

    def test_email_section_includes_public_base_and_from(self):
        """Report resend_ready, PUBLIC_BASE_URL, and from address."""
        payload = platform_health_payload(detailed=True)
        self.assertTrue(payload['email']['resend_ready'])
        self.assertEqual(payload['email']['public_base_url'], 'https://tradeflowcolon.com')
        self.assertIn('no-reply@tradeflowcolon.com', payload['email']['default_from_email'])
