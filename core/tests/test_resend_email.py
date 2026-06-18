"""Resend email delivery."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.email_service import enviar_email_transaccional
from core.utils.email_config import explain_email_failure, smtp_configured


class ResendEmailTests(SimpleTestCase):
    def test_explain_resend_not_configured(self):
        msg = explain_email_failure('resend_not_configured')
        self.assertIn('RESEND_API_KEY', msg)

    def test_explain_resend_sandbox(self):
        msg = explain_email_failure('only send testing emails resend.com/domains')
        self.assertIn('Resend', msg)
        self.assertIn('Domains', msg)

    def test_smtp_configured_with_resend_key(self):
        with override_settings(RESEND_API_KEY='re_test', DEBUG=False):
            self.assertTrue(smtp_configured())

    @override_settings(RESEND_API_KEY='re_test', DEBUG=False, DEFAULT_FROM_EMAIL='TF <a@b.com>')
    def test_enviar_via_resend_success(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('urllib.request.urlopen', return_value=mock_resp):
            result = enviar_email_transaccional(
                'buyer@test.pa',
                'Subject',
                '<p>hi</p>',
                'hi',
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.channel, 'resend')

    @override_settings(RESEND_API_KEY='', DEBUG=False)
    def test_enviar_fails_without_key_in_production(self):
        result = enviar_email_transaccional('buyer@test.pa', 'S', '<p>x</p>', 'x')
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, 'resend_not_configured')

    @override_settings(
        RESEND_API_KEY='',
        DEBUG=True,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_debug_console_fallback(self):
        result = enviar_email_transaccional('buyer@test.pa', 'S', '<p>x</p>', 'x')
        self.assertTrue(result.ok)
        self.assertIn('django', result.channel)
