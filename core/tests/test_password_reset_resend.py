"""Password reset must send mail via Resend (not Django console EMAIL_BACKEND)."""
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
        self.assertIn('tradeflowcolon.com', html)
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

    def test_confirm_token_allows_new_password(self):
        """Token from Django generator still works end-to-end for set-password."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token},
        )
        # Django redirects to set-password session URL first.
        first = self.client.get(confirm_url)
        self.assertEqual(first.status_code, 302)
        set_url = first.url
        page = self.client.get(set_url)
        self.assertEqual(page.status_code, 200)

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
