"""Resend transactional email delivery and failure messaging.

Production must refuse to send without RESEND_API_KEY; DEBUG may
fall back to Django mail backends for local CFZ demos.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.email_service import enviar_email_transaccional
from core.utils.email_config import explain_email_failure, smtp_configured


class ResendEmailTests(SimpleTestCase):
    """Assert explain_email_failure and enviar_email_transaccional."""

    def test_explain_resend_not_configured(self):
        """Mention RESEND_API_KEY when Resend is not configured."""
        msg = explain_email_failure('resend_not_configured')
        self.assertIn('RESEND_API_KEY', msg)

    def test_explain_resend_sandbox(self):
        """Explain Resend domain sandbox restrictions clearly."""
        msg = explain_email_failure('only send testing emails resend.com/domains')
        self.assertIn('Resend', msg)
        self.assertIn('Domains', msg)

    def test_smtp_configured_with_resend_key(self):
        """Treat a present RESEND_API_KEY as mail configured."""
        with override_settings(RESEND_API_KEY='re_test', DEBUG=False):
            self.assertTrue(smtp_configured())

    @override_settings(RESEND_API_KEY='re_test', DEBUG=False, DEFAULT_FROM_EMAIL='TF <a@b.com>')
    def test_enviar_via_resend_success(self):
        """Send via Resend SDK and return message id detail."""
        with patch('core.email_service.resend_sdk.Emails.send', return_value={'id': 'msg_123'}):
            result = enviar_email_transaccional(
                'buyer@test.pa',
                'Subject',
                '<p>hi</p>',
                'hi',
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.channel, 'resend')
        self.assertEqual(result.detail, 'msg_123')

    @override_settings(RESEND_API_KEY='', DEBUG=False)
    def test_enviar_fails_without_key_in_production(self):
        """Fail closed in production when RESEND_API_KEY is empty."""
        result = enviar_email_transaccional('buyer@test.pa', 'S', '<p>x</p>', 'x')
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, 'resend_not_configured')

    @override_settings(
        RESEND_API_KEY='',
        DEBUG=True,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_debug_console_fallback(self):
        """Use Django email backend when DEBUG and no Resend key."""
        result = enviar_email_transaccional('buyer@test.pa', 'S', '<p>x</p>', 'x')
        self.assertTrue(result.ok)
        self.assertIn('django', result.channel)
