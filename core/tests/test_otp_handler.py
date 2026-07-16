"""Secure six-digit OTP generation and EmailVerification TTL.

Only one active token per user may exist so replayed codes cannot
bypass the CFZ email gate.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from core.models import EmailVerification, UserProfile
from core.utils.otp_handler import OTP_EXPIRY_MINUTES, generate_user_otp


class OtpHandlerTests(TestCase):
    """Assert generate_user_otp and validity window."""

    def setUp(self):
        """Create unverified buyer for OTP generation."""
        self.user = User.objects.create_user(
            username='otp_user',
            email='otp@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=False)

    def test_generates_six_digit_numeric_code(self):
        """Return a six-digit numeric OTP string."""
        code = generate_user_otp(self.user)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_invalidates_previous_active_tokens(self):
        """Replace prior active EmailVerification rows on regenerate."""
        first = generate_user_otp(self.user)
        second = generate_user_otp(self.user)
        self.assertNotEqual(first, second)
        self.assertEqual(EmailVerification.objects.filter(user=self.user).count(), 1)
        self.assertFalse(
            EmailVerification.objects.filter(user=self.user, code=first).exists()
        )

    def test_persisted_record_is_valid_within_ttl(self):
        """Mark freshly generated records as valid."""
        code = generate_user_otp(self.user)
        record = EmailVerification.objects.get(user=self.user, code=code)
        self.assertTrue(record.is_valid())

    def test_expired_record_is_invalid(self):
        """Treat records older than OTP_EXPIRY_MINUTES as invalid."""
        code = generate_user_otp(self.user)
        record = EmailVerification.objects.get(user=self.user, code=code)
        record.created_at = timezone.now() - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        record.save(update_fields=['created_at'])
        self.assertFalse(record.is_valid())

    def test_generate_for_delegates_to_handler(self):
        """EmailVerification.generate_for uses the secure handler."""
        ev = EmailVerification.generate_for(self.user)
        self.assertEqual(len(ev.code), 6)
        self.assertTrue(ev.is_valid())
