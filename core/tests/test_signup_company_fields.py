"""Signup buyer/seller with company_* POST field names."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.email_service import EmailSendResult
from core.models import UserApplication, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    EXPO_DEMO_MODE=True,
    REQUIRE_EMAIL_VERIFICATION=True,
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class SignupCompanyFieldsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _company_signup_payload(self, username='buyer_co', role='buyer'):
        return {
            'company_first_name': 'Acme',
            'company_last_name': 'Corp',
            'company_username': username,
            'company_email': f'{username}@test.pa',
            'company_phone': '+50760000001',
            'role': role,
            'password1': 'SecurePass1!',
            'password2': 'SecurePass1!',
        }

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_signup_buyer_company_fields_creates_user_and_login(self, mock_send):
        mock_send.return_value = EmailSendResult(ok=True, channel='resend', detail='msg-1')
        payload = self._company_signup_payload(username='buyer_co')

        resp = self.client.post(reverse('signup_buyer'), payload, follow=False)
        self.assertEqual(resp.status_code, 302)

        user = User.objects.get(username='buyer_co')
        self.assertEqual(user.first_name, 'Acme')
        self.assertEqual(user.last_name, 'Corp')
        self.assertEqual(user.email, 'buyer_co@test.pa')

        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'buyer')

        application = UserApplication.objects.get(user=user)
        self.assertEqual(application.phone, '+50760000001')

        self.client.logout()
        login_resp = self.client.post(
            reverse('login'),
            {'username': 'buyer_co', 'password': 'SecurePass1!'},
            follow=False,
        )
        self.assertEqual(login_resp.status_code, 302)

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_signup_seller_company_fields_creates_user_and_login(self, mock_send):
        mock_send.return_value = EmailSendResult(ok=True, channel='resend', detail='msg-1')
        payload = self._company_signup_payload(username='seller_co', role='seller')

        resp = self.client.post(reverse('signup_seller'), payload, follow=False)
        self.assertEqual(resp.status_code, 302)

        user = User.objects.get(username='seller_co')
        self.assertEqual(user.first_name, 'Acme')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'seller')

        self.client.logout()
        login_resp = self.client.post(
            reverse('login'),
            {'username': 'seller_co', 'password': 'SecurePass1!'},
            follow=False,
        )
        self.assertEqual(login_resp.status_code, 302)

    @patch('core.views_onboarding.enviar_codigo_verificacion')
    def test_signup_buyer_get_renders_company_labels(self, mock_send):
        resp = self.client.get(reverse('signup_buyer'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('name="company_first_name"', content)
        self.assertIn('name="company_username"', content)
        self.assertIn('name="password1"', content)
        self.assertIn('name="password2"', content)
        self.assertNotIn('name="first_name"', content)
        self.assertNotIn('name="username"', content)
