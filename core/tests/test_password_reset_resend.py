"""DB-backed password reset links with Resend delivery.

Magic links are single-use and TTL-bound so CFZ operators and
buyers can recover accounts without leaking email existence.
"""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.email_service import EmailSendResult
from core.enterprise_models import EmailDeliveryLog
from core.models import PasswordResetLink
from core.utils.password_reset_link import (
    PASSWORD_RESET_LINK_EXPIRY_MINUTES,
    generate_password_reset_link,
)
from core.utils.secret_hash import hash_secret

User = get_user_model()


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEFAULT_FROM_EMAIL='TradeFlow Colón <no-reply@tradeflowcolon.com>',
    RESEND_API_KEY='re_test_key',
    LANGUAGE_CODE='en',
    PASSWORD_RESET_TIMEOUT=60 * 15,
)
class PasswordResetDbLinkTests(TestCase):
    """Assert PasswordResetLink create, consume, and expiry paths."""

    def setUp(self):
        """Activate language and create a user with mixed-case email."""
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
    def test_reset_persists_db_token_and_sends_via_resend(self, mock_send):
        """Persist token, email via Resend, and log delivery."""
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'reset.user@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))

        link = PasswordResetLink.objects.get(user=self.user, is_used=False)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        to_email, subject, html, text = args[:4]
        self.assertEqual(to_email.lower(), 'reset.user@example.com')
        # Email carries the plaintext token; DB stores only the digest.
        self.assertEqual(len(link.token), 64)
        self.assertIn('/recuperar-clave/confirmar/', text)
        self.assertIn('/recuperar-clave/confirmar/', html)
        # Extract token from confirm URL and verify it matches the stored hash.
        import re
        m = re.search(r'/recuperar-clave/confirmar/[^/]+/([^/\s]+)/?', text)
        self.assertIsNotNone(m)
        self.assertEqual(link.token, hash_secret(m.group(1)))
        self.assertEqual(kwargs.get('tipo'), 'password_reset')
        self.assertEqual(
            EmailDeliveryLog.objects.filter(
                email_type='password_reset', status='sent'
            ).count(),
            1,
        )

    @patch('core.email_service.enviar_email_transaccional')
    def test_unknown_email_still_shows_done_without_send(self, mock_send):
        """Show done page for unknown emails without sending mail."""
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'nobody@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_done'))
        mock_send.assert_not_called()
        self.assertEqual(PasswordResetLink.objects.count(), 0)

    def test_confirm_sets_password_autologin_and_consumes_link(self):
        """Set password, autologin, and delete the consumed link."""
        token = generate_password_reset_link(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token},
        )
        first = self.client.get(confirm_url)
        self.assertEqual(first.status_code, 302)
        set_url = first.url
        self.assertEqual(self.client.get(set_url).status_code, 200)

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
        self.assertEqual(str(self.client.session.get('_auth_user_id')), str(self.user.pk))
        self.assertFalse(
            PasswordResetLink.objects.filter(
                user=self.user, token=hash_secret(token),
            ).exists()
        )

        complete = self.client.get(reverse('password_reset_complete'))
        self.assertContains(complete, 'You are signed in')

    def test_invalid_token_shows_safe_page(self):
        """Render expired/invalid messaging for bad tokens."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': 'not-a-real-token'},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link expired or invalid')

    def test_expired_token_rejected(self):
        """Reject tokens aged past PASSWORD_RESET_LINK_EXPIRY."""
        token = generate_password_reset_link(self.user)
        row = PasswordResetLink.objects.get(token=hash_secret(token))
        # Age created_at beyond TTL without storing secrets in logs.
        from django.utils import timezone
        from datetime import timedelta

        PasswordResetLink.objects.filter(pk=row.pk).update(
            created_at=timezone.now()
            - timedelta(minutes=PASSWORD_RESET_LINK_EXPIRY_MINUTES + 1)
        )
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(
            reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': token},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link expired or invalid')

    def test_token_cannot_be_reused(self):
        """Reject a second visit after successful password change."""
        token = generate_password_reset_link(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
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
        again = self.client.get(confirm_url)
        self.assertEqual(again.status_code, 200)
        self.assertContains(again, 'Link expired or invalid')

    def test_new_request_invalidates_previous_link(self):
        """Invalidate prior unused links when a new reset is issued."""
        first = generate_password_reset_link(self.user)
        second = generate_password_reset_link(self.user)
        self.assertNotEqual(first, second)
        self.assertFalse(
            PasswordResetLink.objects.filter(token=hash_secret(first)).exists()
        )
        self.assertTrue(
            PasswordResetLink.objects.filter(token=hash_secret(second)).exists()
        )
