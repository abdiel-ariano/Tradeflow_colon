"""
Verificación de email por código OTP de 6 dígitos.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import UserProfile
from core.utils.email_verification import assign_email_verification_code, verify_email_code


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    REQUIRE_EMAIL_VERIFICATION=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class EmailVerificationOtpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='otp_buyer',
            email='otp@test.pa',
            password='TestPass123!',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=False,
        )
        self.client = Client()

    def test_verify_code_success(self):
        code = assign_email_verification_code(self.profile)
        ok, err = verify_email_code(self.profile, code)
        self.assertTrue(ok)
        self.assertEqual(err, '')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verificado)

    def test_onboarding_post_code_redirects_tienda(self):
        code = assign_email_verification_code(self.profile)
        self.client.force_login(self.user)
        resp = self.client.post(
            '/onboarding/verificar-codigo/',
            {'codigo': code},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/tienda', resp['Location'])
