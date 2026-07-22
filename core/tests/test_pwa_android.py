"""Tests for the installable PWA and Android trust endpoints."""
from __future__ import annotations

from io import BytesIO

from django.test import SimpleTestCase, override_settings
from PIL import Image


TEST_FINGERPRINT = ':'.join(['AA'] * 32)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'tradeflowcolon.com'],
    ANDROID_APP_PACKAGE='com.tradeflowcolon.app',
    ANDROID_SHA256_CERT_FINGERPRINTS='',
)
class PwaAndroidTests(SimpleTestCase):
    """Validate installability without caching private application data."""

    def test_web_app_manifest_describes_installable_app(self):
        """Expose the names, scope, colors, and required PNG icon sizes."""
        response = self.client.get('/manifest.webmanifest')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'application/manifest+json',
            response['Content-Type'],
        )
        manifest = response.json()
        self.assertEqual(manifest['id'], '/')
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['theme_color'], '#0F2A44')
        self.assertEqual(
            [icon['sizes'] for icon in manifest['icons']],
            ['192x192', '512x512'],
        )

    def test_pwa_icons_have_declared_dimensions(self):
        """Generate exact launcher dimensions from the canonical logo."""
        for size in (192, 512):
            with self.subTest(size=size):
                response = self.client.get(
                    f'/pwa/icon-{size}.png',
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'image/png')
                with Image.open(BytesIO(response.content)) as icon:
                    self.assertEqual(icon.size, (size, size))

    def test_service_worker_has_root_scope_and_safe_cache_policy(self):
        """Cache only the public offline shell, never authenticated pages."""
        response = self.client.get('/service-worker.js')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertIn('no-cache', response['Cache-Control'])
        script = response.content.decode('utf-8')
        self.assertIn("const OFFLINE_URL = '/offline/';", script)
        self.assertNotIn('/mi-tienda/', script)
        self.assertNotIn('/dashboard/', script)

    def test_offline_page_is_public(self):
        """Render a usable fallback without requiring a user session."""
        response = self.client.get('/offline/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sin conexión')
        self.assertContains(response, 'Intentar nuevamente')

    def test_assetlinks_stays_empty_without_signing_certificate(self):
        """Avoid claiming an unverified Android relationship by default."""
        response = self.client.get('/.well-known/assetlinks.json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @override_settings(
        ANDROID_SHA256_CERT_FINGERPRINTS=TEST_FINGERPRINT,
    )
    def test_assetlinks_publishes_configured_certificate(self):
        """Bind the website to the configured Android package and key."""
        response = self.client.get('/.well-known/assetlinks.json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(
            payload[0]['target']['package_name'],
            'com.tradeflowcolon.app',
        )
        self.assertEqual(
            payload[0]['target']['sha256_cert_fingerprints'],
            [TEST_FINGERPRINT],
        )
