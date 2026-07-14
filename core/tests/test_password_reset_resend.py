"""Password reset: Resend delivery, 15m timeout, autologin after set-password."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.email_service import EmailSendResult
from core.enterprise_models import EmailDeliveryLog

User = get_user_model()


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEFAULT_FROM_EMAIL='TradeFlow Colón <no-reply@tradeflowcolon.com>',
    RESEND_API_KEY='re_test_key',
    LANGUAGE_CODE='en',
    PASSWORD_RESET_TIMEOUT=60 * 15,
)
class PasswordResetResendTests(TestCase):
    def setUp(self):
        translation.activate(settings.LANGUAGE_CODE)
        self.user = User.objects.create_user(
            username='reset_user',
            email='Reset.User@Example.com',
            password='OldPass123!',
        )

    @patch(
        'core.email_service.enviar_email_transaccional',
        return_value=EmailSendResult(ok=True, channel='resend', detail='msg_reset'),
    )
    def test_reset_posts_email_and_sends_via_resend(self, mock_send):
        """POST known email → done page + Resend called with reset link."""
        url = reverse('password_reset')
        response = self.client.post(url, {'email': 'reset.user@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        to_email, subject, html, text = args[:4]
        self.assertEqual(to_email.lower(), 'reset.user@example.com')
        self.assertIn('Restablecer', subject)
        self.assertIn('tradeflowcolon.com', text)
        self.assertIn('/recuperar-clave/confirmar/', text)
        self.assertIn('15 minutes', text)
        self.assertIn('tradeflowcolon.com', html)
        self.assertIn('/recuperar-clave/confirmar/', html)
        self.assertEqual(kwargs.get('tipo'), 'password_reset')

        self.assertEqual(
            EmailDeliveryLog.objects.filter(
                email_type='password_reset', status='sent'
            ).count(),
            1,
        )

        done = self.client.get(reverse('password_reset_done'))
        self.assertEqual(done.status_code, 200)
        self.assertContains(done, 'Check your email')

    @patch('core.email_service.enviar_email_transaccional')
    def test_unknown_email_still_shows_done_without_send(self, mock_send):
        """Unknown address must not leak existence; same done page, no Resend call."""
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'nobody@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))
        mock_send.assert_not_called()

    @patch(
        'core.email_service.enviar_email_transaccional',
        return_value=EmailSendResult(ok=False, channel='resend', detail='boom'),
    )
    def test_resend_failure_still_redirects_to_done(self, mock_send):
        """Delivery failure is logged; user still sees the safe confirmation page."""
        response = self.client.post(
            reverse('password_reset'),
            {'email': self.user.email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))
        mock_send.assert_called_once()
        self.assertTrue(
            EmailDeliveryLog.objects.filter(
                email_type='password_reset', status='failed'
            ).exists()
        )

    def test_confirm_sets_password_and_autologin(self):
        """Valid magic link → set password → session authenticated (no crash)."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token},
        )
        first = self.client.get(confirm_url)
        self.assertEqual(first.status_code, 302)
        set_url = first.url
        page = self.client.get(set_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'New password')

        response = self.client.post(
            set_url,
            {
                'new_password1': 'NewSecurePass456!',
                'new_password2': 'NewSecurePass456!',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass456!'))
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertEqual(
            str(self.client.session.get('_auth_user_id')),
            str(self.user.pk),
        )

        complete = self.client.get(reverse('password_reset_complete'))
        self.assertEqual(complete.status_code, 200)
        self.assertContains(complete, 'You are signed in')

    def test_invalid_token_shows_safe_page_not_500(self):
        """Malformed/expired token must not crash; show request-again UI."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': 'invalid-token-value'},
        )
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link expired or invalid')
        self.assertContains(response, 'Request a new link')
        self.assertNotContains(response, 'new_password1')

    def test_expired_token_rejected(self):
        """PASSWORD_RESET_TIMEOUT=15m: an aged token fails check_token / UI."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        # Age the token far beyond 15 minutes without storing raw secrets in logs.
        with patch.object(
            default_token_generator,
            '_num_seconds',
            return_value=default_token_generator._num_seconds(
                default_token_generator._now()
            )
            + (60 * 15)
            + 5,
        ):
            self.assertFalse(default_token_generator.check_token(self.user, token))
            confirm_url = reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': token},
            )
            response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link expired or invalid')

    def test_token_cannot_be_reused_after_password_change(self):
        """After password set, the old magic-link token is invalid (single use)."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token},
        )
        set_url = self.client.get(confirm_url).url
        self.client.post(
            set_url,
            {
                'new_password1': 'NewSecurePass456!',
                'new_password2': 'NewSecurePass456!',
            },
        )
        self.client.logout()
        # Fresh client attempting old link again.
        again = self.client.get(confirm_url)
        self.assertEqual(again.status_code, 200)
        self.assertContains(again, 'Link expired or invalid')

    def test_password_reset_timeout_is_fifteen_minutes(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 60 * 15)
