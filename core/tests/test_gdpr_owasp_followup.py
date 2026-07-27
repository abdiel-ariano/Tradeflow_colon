"""Follow-up GDPR/OWASP hardening: uploads, SSRF DNS-pin, staff MFA helpers."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from core.utils import staff_mfa, upload_security
from core.utils.url_validator import SafeOutboundTarget, validate_outbound_url


class UploadSecurityTests(SimpleTestCase):
    """Assert image/PDF upload guards reject bad payloads."""

    def test_accepts_png_image(self):
        """Minimal valid PNG passes image validation."""
        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (1, 1), color=(20, 40, 60)).save(buf, format='PNG')
        png = buf.getvalue()
        uploaded = SimpleUploadedFile('logo.png', png, content_type='image/png')
        out = upload_security.validate_image_upload(uploaded)
        self.assertIs(out, uploaded)

    def test_rejects_exe_as_image(self):
        """Non-image bytes with .png extension are rejected."""
        uploaded = SimpleUploadedFile(
            'evil.png', b'MZ\x90\x00not-an-image', content_type='image/png',
        )
        with self.assertRaises(upload_security.UploadValidationError):
            upload_security.validate_image_upload(uploaded)

    def test_accepts_pdf_proof(self):
        """PDF magic header is required for proof uploads."""
        uploaded = SimpleUploadedFile(
            'proof.pdf', b'%PDF-1.4 fake', content_type='application/pdf',
        )
        out = upload_security.validate_proof_upload(uploaded)
        self.assertIs(out, uploaded)

    def test_rejects_oversized(self):
        """Files above max_bytes are rejected."""
        uploaded = SimpleUploadedFile(
            'big.png', b'\x89PNG\r\n\x1a\n' + b'x' * 100, content_type='image/png',
        )
        with self.assertRaises(upload_security.UploadValidationError) as ctx:
            upload_security.validate_image_upload(uploaded, max_bytes=20)
        self.assertEqual(str(ctx.exception), 'too_large')


class UrlValidatorSsrfTests(SimpleTestCase):
    """Assert outbound URL validation blocks private targets."""

    def test_blocks_metadata_ip(self):
        """Cloud metadata IP must be rejected."""
        with self.assertRaises(ValidationError):
            validate_outbound_url('https://169.254.169.254/latest/meta-data/')

    def test_blocks_localhost(self):
        """localhost hostname must be rejected."""
        with self.assertRaises(ValidationError):
            validate_outbound_url('https://localhost/hook')

    @patch('core.utils.url_validator._resolve_hostname')
    def test_returns_safe_target_for_public_host(self, mock_resolve):
        """Public resolution yields SafeOutboundTarget with pinned IPs."""
        import ipaddress

        mock_resolve.return_value = [ipaddress.ip_address('8.8.8.8')]
        target = validate_outbound_url('https://hooks.example.com/dispatch')
        self.assertIsInstance(target, SafeOutboundTarget)
        self.assertEqual(target.hostname, 'hooks.example.com')
        self.assertEqual(target.ips, ('8.8.8.8',))


class StaffMfaHelperTests(TestCase):
    """Assert TOTP enablement and verify helpers."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='staff_mfa',
            email='staff@example.com',
            password='TestPass123!',
            is_staff=True,
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'admin'
        self.profile.save()

    @override_settings(STAFF_MFA_REQUIRED=False, EXPO_DEMO_MODE=False)
    def test_user_needs_mfa_only_when_enabled_if_not_required(self):
        """When MFA is not required, only enrolled staff are challenged."""
        self.assertFalse(staff_mfa.user_needs_staff_mfa(self.user))
        secret = staff_mfa.generate_totp_secret()
        self.profile.staff_totp_secret = staff_mfa.encrypt_totp_secret(secret)
        self.profile.staff_totp_enabled = True
        self.profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
        self.user.refresh_from_db()
        self.assertTrue(staff_mfa.user_needs_staff_mfa(self.user))

    @override_settings(STAFF_MFA_REQUIRED=True, EXPO_DEMO_MODE=False)
    def test_staff_mfa_required_forces_setup(self):
        """Required MFA challenges staff even before TOTP enrollment."""
        self.assertTrue(staff_mfa.user_needs_staff_mfa(self.user))
        self.assertTrue(staff_mfa.user_needs_staff_mfa_setup(self.user))

    @override_settings(
        STAFF_MFA_REQUIRED=True,
        EXPO_DEMO_MODE=False,
        SAAS_DEMO_ADMIN_USERNAME='staff_mfa',
    )
    def test_demo_admin_skips_forced_mfa(self):
        """The configured demo administrator does not enroll in MFA."""
        self.assertFalse(staff_mfa.user_needs_staff_mfa(self.user))
        self.assertFalse(staff_mfa.user_needs_staff_mfa_setup(self.user))

    @override_settings(STAFF_MFA_REQUIRED=True, EXPO_DEMO_MODE=True)
    def test_expo_demo_skips_forced_mfa(self):
        """Expo demo mode keeps MFA optional for staff."""
        self.assertFalse(staff_mfa.user_needs_staff_mfa(self.user))
        self.assertFalse(staff_mfa.user_needs_staff_mfa_setup(self.user))

    def test_verify_totp_roundtrip(self):
        """A current TOTP code verifies against the encrypted secret."""
        import pyotp

        secret = staff_mfa.generate_totp_secret()
        self.profile.staff_totp_secret = staff_mfa.encrypt_totp_secret(secret)
        self.profile.staff_totp_enabled = True
        self.profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
        code = pyotp.TOTP(secret).now()
        self.assertTrue(staff_mfa.verify_totp(self.user, code))
        self.assertFalse(staff_mfa.verify_totp(self.user, '000000'))

    def test_session_mfa_flag(self):
        """Session MFA ok flag can be set and cleared."""
        factory = RequestFactory()
        request = factory.get('/')
        request.session = self.client.session
        self.assertFalse(staff_mfa.session_mfa_ok(request))
        staff_mfa.mark_session_mfa_ok(request)
        self.assertTrue(staff_mfa.session_mfa_ok(request))
        staff_mfa.clear_session_mfa(request)
        self.assertFalse(staff_mfa.session_mfa_ok(request))

    def test_backup_codes_consume_once_and_survive_key_change(self):
        """Backup codes work once and remain valid after SECRET_KEY rotation."""
        secret = staff_mfa.generate_totp_secret()
        self.profile.staff_totp_secret = staff_mfa.encrypt_totp_secret(secret)
        self.profile.staff_totp_enabled = True
        self.profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
        codes = staff_mfa.generate_backup_codes(count=2)
        staff_mfa.store_backup_code_hashes(self.profile, codes)
        self.assertEqual(staff_mfa.remaining_backup_codes(self.profile), 2)

        with override_settings(SECRET_KEY='rotated-secret-key-for-mfa-test-32b'):
            # TOTP decrypt fails after rotation; backup still works.
            self.assertTrue(staff_mfa.totp_decrypt_broken(self.user))
            self.assertTrue(staff_mfa.verify_staff_mfa_code(self.user, codes[0]))
            self.profile.refresh_from_db()
            self.assertEqual(staff_mfa.remaining_backup_codes(self.profile), 1)
            self.assertFalse(staff_mfa.consume_backup_code(self.user, codes[0]))

    def test_reset_staff_mfa_command(self):
        """Management command clears TOTP and backup hashes."""
        from django.core.management import call_command

        secret = staff_mfa.generate_totp_secret()
        self.profile.staff_totp_secret = staff_mfa.encrypt_totp_secret(secret)
        self.profile.staff_totp_enabled = True
        self.profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
        staff_mfa.store_backup_code_hashes(self.profile, staff_mfa.generate_backup_codes(2))
        call_command('reset_staff_mfa', self.user.username, yes=True)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.staff_totp_enabled)
        self.assertEqual(self.profile.staff_totp_secret, '')
        self.assertEqual(self.profile.staff_totp_backup_hashes, [])


@override_settings(
    STAFF_MFA_REQUIRED=True,
    EXPO_DEMO_MODE=False,
    SAAS_DEMO_ADMIN_USERNAME='demo_admin',
)
class DemoAdminAccessTests(TestCase):
    """Verify the walkthrough administrator can operate every admin screen."""

    def setUp(self):
        """Create and authenticate the configured demonstration operator."""
        self.user = User.objects.create_user(
            username='demo_admin',
            email='demo.admin@tradeflow.pa',
            password='TestPass123!',
            is_staff=True,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = 'admin'
        profile.email_verificado = True
        profile.save(update_fields=['role', 'email_verificado'])
        self.client.force_login(self.user)

    def test_saas_dashboard_has_no_read_only_banner(self):
        """The SaaS panel exposes the normal writable administration shell."""
        response = self.client.get(reverse('admin_saas_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Read-only demo')
        self.assertContains(response, 'class="adm-rail-link"', count=15)

    def test_django_admin_is_available(self):
        """Every configured demo operator can enter Django Admin directly."""
        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)

    def test_saas_mutation_reaches_the_real_action(self):
        """The middleware does not reject writable SaaS requests."""
        url = reverse('api_admin_saas_request_action', kwargs={'pk': 999})
        response = self.client.post(
            url,
            data='{"action": "approve"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'Application not found'})

