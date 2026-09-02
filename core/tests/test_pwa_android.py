"""Tests for the installable PWA and Android trust endpoints."""
from __future__ import annotations

from io import BytesIO

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from core.android_assetlinks import validate_asset_links


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


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'tradeflowcolon.com'],
    LANGUAGE_CODE='en',
)
class PwaInstallButtonTests(TestCase):
    """Validate compact install control markup and i18n on public pages."""

    def setUp(self):
        translation.activate(settings.LANGUAGE_CODE)
        self.client = Client()

    def test_install_button_is_hidden_compact_and_wired_to_pwa_script(self):
        """Expose a hidden install control with compact markup and assets."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tf-install-app')
        self.assertContains(response, 'hidden')
        self.assertContains(response, 'class="tf-install-app"')
        self.assertContains(response, 'tf-install-app__label')
        self.assertContains(response, 'Install App')
        self.assertContains(response, 'aria-label="Install App"')
        self.assertContains(response, 'tf-mobile-pwa.css')
        self.assertContains(response, 'tf-mobile-pwa.js')

    def test_install_button_label_switches_with_language(self):
        """Spanish locale shows the translated install label."""
        self.client.cookies['django_language'] = 'es'
        response = self.client.get('/es' + reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Instalar app')
        self.assertContains(response, 'aria-label="Instalar app"')
        self.assertNotContains(response, 'Install App')

    def test_marketplace_mobile_styles_lock_horizontal_overflow(self):
        """Home and catalog ship Android overflow containment rules."""
        for url_name in ('home', 'catalogo_publico'):
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'tf-mobile-pwa.css')
                css_path = settings.BASE_DIR / 'static' / 'css' / 'tf-mobile-pwa.css'
                css = css_path.read_text(encoding='utf-8')
                self.assertIn('overscroll-behavior-x: none', css)
                self.assertIn('overflow-x: hidden', css)
                self.assertIn('position: fixed', css)
                self.assertIn('tf-market-menu-open', css)


class AndroidAssetLinksValidationTests(SimpleTestCase):
    """Validate the certificate guard used by production Android builds."""

    def build_statement(
        self,
        fingerprint: str = TEST_FINGERPRINT,
        package_name: str = 'com.tradeflowcolon.app',
    ) -> dict:
        """Return one standards-compliant Android association statement."""
        return {
            'relation': [
                'delegate_permission/common.handle_all_urls',
            ],
            'target': {
                'namespace': 'android_app',
                'package_name': package_name,
                'sha256_cert_fingerprints': [fingerprint],
            },
        }

    def test_empty_document_blocks_production_build(self):
        """Reject the live site's current unconfigured empty document."""
        is_valid, message = validate_asset_links(
            [],
            'com.tradeflowcolon.app',
            TEST_FINGERPRINT,
        )

        self.assertFalse(is_valid)
        self.assertIn('no Android association', message)

    def test_matching_statement_allows_production_build(self):
        """Accept the package only when the signing fingerprint matches."""
        is_valid, message = validate_asset_links(
            [self.build_statement()],
            'com.tradeflowcolon.app',
            TEST_FINGERPRINT,
        )

        self.assertTrue(is_valid)
        self.assertIn('matches', message)

    def test_wrong_certificate_blocks_production_build(self):
        """Reject a package signed with an unlisted certificate."""
        other_fingerprint = ':'.join(['BB'] * 32)
        is_valid, message = validate_asset_links(
            [self.build_statement()],
            'com.tradeflowcolon.app',
            other_fingerprint,
        )

        self.assertFalse(is_valid)
        self.assertIn('does not match', message)
