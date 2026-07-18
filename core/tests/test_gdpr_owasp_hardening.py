"""Regression coverage for GDPR DSAR + OWASP hardening changes."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import EmailVerification, PasswordResetLink, UserProfile
from core.utils.otp_handler import generate_user_otp
from core.utils.otp_verification import verify_user_otp
from core.utils.password_reset_link import (
    consume_password_reset_link,
    generate_password_reset_link,
)
from core.utils.privacy import anonymize_user, build_user_export
from core.utils.secret_hash import hash_secret
from core.utils.sql_guard import assert_readonly_sql


class TestSqlGuard(SimpleTestCase):
    def test_allows_select(self):
        self.assertTrue(assert_readonly_sql('SELECT 1').startswith('SELECT'))

    def test_blocks_mutating(self):
        with self.assertRaises(ValueError):
            assert_readonly_sql('DELETE FROM core_userprofile')
        with self.assertRaises(ValueError):
            assert_readonly_sql('SELECT 1; DROP TABLE x')


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False)
class TestSecretHashing(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hash_user', email='hash@example.com', password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer')

    def test_otp_stored_hashed(self):
        plain = generate_user_otp(self.user)
        row = EmailVerification.objects.get(user=self.user)
        self.assertEqual(row.code, hash_secret(plain))
        self.assertNotEqual(row.code, plain)
        result = verify_user_otp(self.user, plain)
        self.assertTrue(result.ok)

    def test_password_reset_stored_hashed(self):
        plain = generate_password_reset_link(self.user)
        row = PasswordResetLink.objects.get(user=self.user)
        self.assertEqual(row.token, hash_secret(plain))
        consumed = consume_password_reset_link(user=self.user, raw_token=plain)
        self.assertTrue(consumed.ok)


@override_settings(AXES_ENABLED=False, REQUIRE_EMAIL_VERIFICATION=False, SECURE_SSL_REDIRECT=False)
class TestPrivacyDsar(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='gdpr_user', email='gdpr@example.com', password='TestPass123!',
            first_name='Ada', last_name='Lovelace',
        )
        UserProfile.objects.create(
            user=self.user, role='buyer', phone='555', marketing_opt_in=True,
        )

    def test_export_contains_profile(self):
        payload = build_user_export(self.user)
        self.assertEqual(payload['user']['email'], 'gdpr@example.com')
        self.assertTrue(payload['profile']['marketing_opt_in'])

    def test_anonymize_scrubs_pii(self):
        anonymize_user(self.user)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIn('anonymized.invalid', self.user.email)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, '')
        self.assertIsNotNone(self.user.profile.account_anonymized_at)

    def test_export_endpoint(self):
        self.client.login(username='gdpr_user', password='TestPass123!')
        r = self.client.post(reverse('mi_perfil'), {'action': 'export_data'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/json', r['Content-Type'])
        self.assertIn(b'gdpr@example.com', r.content)


@override_settings(AXES_ENABLED=False, SECURE_SSL_REDIRECT=False)
class TestHealthReadyPublic(TestCase):
    def test_public_health_hides_debug(self):
        r = self.client.get(reverse('health_ready'))
        self.assertIn(r.status_code, (200, 503))
        data = r.json()
        self.assertNotIn('debug', data)
        self.assertNotIn('email', data)
        self.assertIn('database', data)
