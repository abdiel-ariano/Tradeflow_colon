"""Email verification OTP (EmailVerification) for buyer signup.

Six-digit codes unlock catalog or onboarding depending on whether the
buyer already completed preferences after registering.
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
    """Assert OTP validity and post-verify redirect destinations."""

    def setUp(self):
        """Create an unverified buyer profile for OTP flows."""
        self.user = User.objects.create_user(
            username='otp_buyer',
            email='otp@test.pa',
            password='TestPass123!',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=False,
            onboarding_completed_at=None,
        )
        self.client = Client()

    def test_generate_and_validate(self):
        """Generated codes are 6 digits; used codes fail is_valid()."""
        ev = EmailVerification.generate_for(self.user)
        self.assertEqual(len(ev.code), 6)
        self.assertTrue(ev.is_valid())
        ev.is_used = True
        ev.save(update_fields=['is_used'])
        self.assertFalse(ev.is_valid())

    def test_verificar_codigo_post_redirects_catalogo(self):
        """Verified buyers with completed onboarding go to /catalogo/."""
        from django.utils import timezone

        # Account already completed onboarding (existing-user path).
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.save(update_fields=['onboarding_completed_at'])
        ev = EmailVerification.generate_for(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(
            '/verificar/',
            {'codigo': ev.code},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            '/catalogo' in resp['Location'] or resp['Location'].endswith('/catalogo/'),
        )
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)

    def test_verificar_codigo_new_buyer_redirects_onboarding(self):
        """Newly verified buyers without onboarding go to buyer wizard."""
        ev = EmailVerification.generate_for(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(
            '/verificar/',
            {'codigo': ev.code},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/onboarding/comprador', resp['Location'])
