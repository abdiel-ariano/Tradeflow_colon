"""
Verificación de email por código OTP de 6 dígitos (modelo EmailVerification).
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import EmailVerification, UserProfile


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

    def test_generate_and_validate(self):
        ev = EmailVerification.generate_for(self.user)
        self.assertEqual(len(ev.code), 6)
        self.assertTrue(ev.is_valid())
        ev.is_used = True
        ev.save(update_fields=['is_used'])
        self.assertFalse(ev.is_valid())

    def test_verificar_codigo_post_redirects_tienda(self):
        ev = EmailVerification.generate_for(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(
            '/verificar/',
            {'codigo': ev.code},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            '/tienda' in resp['Location'] or resp['Location'].endswith('/tienda/'),
        )
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)
