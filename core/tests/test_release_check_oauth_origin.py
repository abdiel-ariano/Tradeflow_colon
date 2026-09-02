"""Regression coverage for production release configuration gates."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


_GOOGLE_CONFIG = {
    'google': {
        'APP': {
            'client_id': 'configured-client-id',
            'secret': 'configured-client-secret',
        },
    },
}


@override_settings(
    DEBUG=False,
    SECRET_KEY='release-test-secret',
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}},
    STORAGES={
        'default': {'BACKEND': 'storages.backends.s3.S3Storage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
    REQUIRE_EMAIL_VERIFICATION=True,
    EMAIL_USE_REAL_SMTP=True,
    SUPABASE_CONFIGURED=False,
    EXPO_DEMO_MODE=False,
    STAFF_MFA_REQUIRED=True,
    SERVE_LOCAL_MEDIA=False,
    SOCIALACCOUNT_PROVIDERS=_GOOGLE_CONFIG,
)
class ReleaseCheckOAuthOriginTests(SimpleTestCase):
    """Block deploys with malformed origins or half-configured OAuth."""

    @patch(
        'core.management.commands.release_check.platform_health_payload',
        return_value={'database': {'ok': True}},
    )
    @patch(
        'core.management.commands.release_check.validate_email_infrastructure',
        return_value=[],
    )
    def test_valid_public_origin_and_google_credentials_pass(
        self,
        _validate_email,
        _platform_health,
    ):
        output = StringIO()

        call_command('release_check', stdout=output)

        self.assertIn('Release check: OK', output.getvalue())

    @override_settings(PUBLIC_BASE_URL='http://tradeflowcolon.com/login/')
    @patch(
        'core.management.commands.release_check.platform_health_payload',
        return_value={'database': {'ok': True}},
    )
    @patch(
        'core.management.commands.release_check.validate_email_infrastructure',
        return_value=[],
    )
    def test_non_https_origin_with_path_is_blocked(
        self,
        _validate_email,
        _platform_health,
    ):
        with self.assertRaises(SystemExit):
            call_command('release_check', stdout=StringIO())

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            'google': {
                'APP': {
                    'client_id': 'configured-client-id',
                    'secret': '',
                },
            },
        },
    )
    @patch(
        'core.management.commands.release_check.platform_health_payload',
        return_value={'database': {'ok': True}},
    )
    @patch(
        'core.management.commands.release_check.validate_email_infrastructure',
        return_value=[],
    )
    def test_partial_google_credentials_are_blocked(
        self,
        _validate_email,
        _platform_health,
    ):
        with self.assertRaises(SystemExit):
            call_command('release_check', stdout=StringIO())
