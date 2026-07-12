"""Tests for secure OTP generation (otp_handler)."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from core.models import EmailVerification, UserProfile
from core.utils.otp_handler import OTP_EXPIRY_MINUTES, generate_user_otp


class OtpHandlerTests(TestCase):
    def setUp(self):
        """Setup."""
        self.user = User.objects.create_user(
            username='otp_user',
            email='otp@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=False)

    def test_generates_six_digit_numeric_code(self):
        """Test generates six digit numeric code."""
        code = generate_user_otp(self.user)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_invalidates_previous_active_tokens(self):
        """Test invalidates previous active tokens."""
        first = generate_user_otp(self.user)
        second = generate_user_otp(self.user)
        self.assertNotEqual(first, second)
        self.assertEqual(EmailVerification.objects.filter(user=self.user).count(), 1)
        self.assertFalse(
            EmailVerification.objects.filter(user=self.user, code=first).exists()
        )

    def test_persisted_record_is_valid_within_ttl(self):
        """Test persisted record is valid within ttl."""
        code = generate_user_otp(self.user)
        record = EmailVerification.objects.get(user=self.user, code=code)
        self.assertTrue(record.is_valid())

    def test_expired_record_is_invalid(self):
        """Test expired record is invalid."""
        code = generate_user_otp(self.user)
        record = EmailVerification.objects.get(user=self.user, code=code)
        record.created_at = timezone.now() - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        record.save(update_fields=['created_at'])
        self.assertFalse(record.is_valid())

    def test_generate_for_delegates_to_handler(self):
        """Test generate for delegates to handler."""
        ev = EmailVerification.generate_for(self.user)
        self.assertEqual(len(ev.code), 6)
        self.assertTrue(ev.is_valid())
