"""Email OTP verification view and verify_user_otp utility.

Checkout next URLs and JSON clients complete verification;
tokens are deleted after success to block replay.
"""
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import EmailVerification, UserApplication, UserProfile
from core.utils.otp_handler import generate_user_otp
from core.utils.otp_verification import verify_user_otp


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    REQUIRE_EMAIL_VERIFICATION=True,
    EXPO_DEMO_MODE=False,
    AXES_ENABLED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class VerifyOtpViewTests(TestCase):
    """Assert GET/POST verify flows and replay protection."""

    def setUp(self):
        """Log in an unverified buyer for OTP verification."""
        self.user = User.objects.create_user(
            username='otp_view_user',
            email='otp_view@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=False,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_get_renders_form(self):
        """Render the verify email form on GET."""
        resp = self.client.get(reverse('verificar_codigo'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Verify')

    def test_post_valid_code_redirects_to_checkout_next(self):
        """Honor next=/checkout/ after a valid OTP POST."""
        code = generate_user_otp(self.user)
        resp = self.client.post(
            reverse('verificar_codigo') + '?next=/checkout/',
            {'codigo': code, 'next': '/checkout/'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/checkout/')

    def test_post_valid_code_json(self):
        """Return JSON ok/redirect and mark email verified."""
        code = generate_user_otp(self.user)
        resp = self.client.post(
            reverse('verificar_codigo') + '?format=json',
            {'codigo': code},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertIn('redirect', data)
        self.profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(self.profile.email_verificado)
        self.assertFalse(EmailVerification.objects.filter(user=self.user).exists())

    def test_post_invalid_code_returns_400_json(self):
        """Return 400 JSON when the code does not match."""
        generate_user_otp(self.user)
        resp = self.client.post(
            reverse('verificar_codigo') + '?format=json',
            {'codigo': '000000'},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data['ok'])

    def test_expo_demo_mode_approves_application(self):
        """Approve UserApplication and activate user in expo demo."""
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        code = generate_user_otp(self.user)
        with override_settings(EXPO_DEMO_MODE=True):
            result = verify_user_otp(self.user, code)
        self.assertTrue(result.ok)
        app = UserApplication.objects.get(user=self.user)
        self.assertEqual(app.status, 'approved')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_verify_deletes_token_replay_protection(self):
        """Reject a second verify attempt with the same code."""
        code = generate_user_otp(self.user)
        first = verify_user_otp(self.user, code)
        self.assertTrue(first.ok)
        second = verify_user_otp(self.user, code)
        self.assertFalse(second.ok)
