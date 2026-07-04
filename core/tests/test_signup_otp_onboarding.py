"""Registro en EXPO_DEMO_MODE: OTP + correo + sesión + redirect a /verificar/."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.email_service import EmailSendResult
from core.models import EmailVerification, UserProfile
from core.views_onboarding import SESSION_PENDING_VERIFY_USER_ID


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    EXPO_DEMO_MODE=True,
    REQUIRE_EMAIL_VERIFICATION=False,
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class SignupOtpOnboardingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _signup_payload(self, username='demo_new'):
        return {
            'first_name': 'Demo',
            'last_name': 'User',
            'username': username,
            'email': f'{username}@test.pa',
            'phone': '+50760000000',
            'role': 'buyer',
            'password1': 'SecurePass1!',
            'password2': 'SecurePass1!',
        }

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_signup_expo_demo_sends_otp_and_redirects_verificar(self, mock_send):
        mock_send.return_value = EmailSendResult(ok=True, channel='resend', detail='msg-1')

        resp = self.client.post(reverse('signup'), self._signup_payload(), follow=False)

        self.assertEqual(resp.status_code, 302)
        self.assertIn('/verificar', resp['Location'])

        user = User.objects.get(username='demo_new')
        self.assertTrue(user.is_active)
        self.assertTrue(EmailVerification.objects.filter(user=user).exists())
        mock_send.assert_called_once()
        sent_email, sent_code = mock_send.call_args[0]
        self.assertEqual(sent_email, 'demo_new@test.pa')
        self.assertEqual(len(sent_code), 6)

        session = self.client.session
        self.assertEqual(session.get(SESSION_PENDING_VERIFY_USER_ID), user.pk)

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_signup_expo_demo_email_failure_still_redirects_with_warning(self, mock_send):
        mock_send.side_effect = RuntimeError('Resend API key invalid')

        resp = self.client.post(
            reverse('signup'),
            self._signup_payload(username='demo_warn'),
            follow=True,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('/verificar', resp.request['PATH_INFO'])
        user = User.objects.get(username='demo_warn')
        self.assertTrue(user.is_active)
        self.assertTrue(EmailVerification.objects.filter(user=user).exists())

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_verificar_renders_without_redirect_loop_expo_demo(self, mock_send):
        mock_send.return_value = EmailSendResult(ok=True, channel='resend', detail='msg-1')
        self.client.post(reverse('signup'), self._signup_payload(username='demo_loop'), follow=False)
        resp = self.client.get('/verificar/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.redirect_chain), 1)
        self.assertContains(resp, 'Verify your email')

    @override_settings(EXPO_DEMO_MODE=False)
    def test_signup_non_demo_stays_pending_approval(self):
        resp = self.client.post(reverse('signup'), self._signup_payload(username='classic'), follow=False)

        self.assertEqual(resp.status_code, 302)
        self.assertIn('pending', resp['Location'])
        user = User.objects.get(username='classic')
        self.assertFalse(user.is_active)
