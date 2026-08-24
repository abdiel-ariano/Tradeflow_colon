"""Public deployment diagnostics exposed by the readiness payload."""
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.utils.platform_health import platform_health_payload


_DB_OK = {'ok': True, 'detail': 'connected', 'latency_ms': 1.0}


class PlatformHealthDeploymentTests(SimpleTestCase):
    """Keep build identity and OAuth readiness visible without secrets."""

    @patch.dict(
        os.environ,
        {
            'RAILWAY_GIT_COMMIT_SHA': '96fefe6ab42b919d393a041c04e98b6a42b25078',
            'RAILWAY_ENVIRONMENT_NAME': 'production',
        },
    )
    @patch('core.utils.platform_health.check_database', return_value=_DB_OK)
    def test_public_payload_identifies_running_deployment(self, _check_database):
        payload = platform_health_payload()

        self.assertEqual(payload['deployment']['commit'], '96fefe6ab42b')
        self.assertEqual(payload['deployment']['environment'], 'production')

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            'google': {
                'APP': {
                    'client_id': 'configured-client-id',
                    'secret': 'configured-client-secret',
                },
            },
        },
    )
    @patch('core.utils.platform_health.check_database', return_value=_DB_OK)
    def test_public_payload_reports_enabled_oauth_without_secrets(
        self,
        _check_database,
    ):
        payload = platform_health_payload()

        self.assertEqual(payload['auth']['oauth_providers'], ['google'])
        rendered = str(payload)
        self.assertNotIn('configured-client-id', rendered)
        self.assertNotIn('configured-client-secret', rendered)
