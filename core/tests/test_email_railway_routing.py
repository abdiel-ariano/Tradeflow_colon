"""Email routing on Railway vs Supabase Edge Function."""
from django.test import SimpleTestCase, override_settings

from core.email_service import _is_non_retryable_delivery_error, enviar_email_transaccional
from core.utils.email_config import explain_email_failure, is_railway_deploy


class EmailRailwayRoutingTests(SimpleTestCase):
    def test_resend_sandbox_is_non_retryable(self):
        detail = 'only send testing emails to your own email address resend.com'
        self.assertTrue(_is_non_retryable_delivery_error(detail))

    def test_explain_resend_sandbox(self):
        msg = explain_email_failure('only send testing emails resend.com/domains')
        self.assertIn('send-transactional-email', msg)
        self.assertIn('bright-handler', msg)

    def test_explain_not_found(self):
        msg = explain_email_failure('NOT_FOUND Requested function was not found')
        self.assertIn('desplegada', msg.lower())

    @override_settings(
        SUPABASE_EMAIL_ENABLED=True,
        SUPABASE_CONFIGURED=True,
        SUPABASE_URL='https://x.supabase.co',
        SUPABASE_SERVICE_KEY='key',
        EMAIL_SMTP_CONFIGURED=True,
        EMAIL_SMTP_FALLBACK_ENABLED=False,
        RAILWAY_DEPLOY=True,
    )
    def test_skips_smtp_on_railway_after_supabase_reject(self):
        from unittest.mock import patch

        reject_detail = (
            'HTTP Error 400 — {"error":"validation_error only send testing emails resend"}'
        )
        with patch('core.email_service._send_via_supabase') as mock_sb:
            mock_sb.return_value = type('R', (), {'ok': False, 'detail': reject_detail})()
            result = enviar_email_transaccional(
                'other@gmail.com',
                'Subject',
                '<p>hi</p>',
                'hi',
                tipo='access_decision',
            )
        self.assertFalse(result.ok)
        self.assertIn('validation_error', result.detail.lower() or reject_detail.lower())
