"""Unified floating toast notifications."""
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class UnifiedToastTests(TestCase):
    """Toast assets and integration contract."""

    def test_base_includes_toast_stylesheet(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('css/tf-toasts.css', body)
        self.assertIn('id="tf-toast-root"', body)
        self.assertIn('tf_notifications.js', body)

    def test_notifications_js_has_unified_api(self):
        js = Path('static/js/tf_notifications.js').read_text(encoding='utf-8')
        self.assertIn('global.tfNotify = tfNotify', js)
        self.assertIn('TF_FLASH_MESSAGES', js)
        self.assertIn('AUTO_DISMISS_MS', js)
        self.assertIn('dedupeKey', js)
        self.assertIn("'tf-toast tf-toast--' + level", js)
        self.assertIn('tf-toast__close', js)
        self.assertNotIn('tf-cart-snackbar', js)

    def test_toast_css_positions_top_right(self):
        css = Path('static/css/tf-toasts.css').read_text(encoding='utf-8')
        self.assertIn('.tf-toast-root', css)
        self.assertIn('width: min(360px', css)
        self.assertIn('border-left-width: 4px', css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn('tf-flash-stack--noscript', css)

    def test_cart_ajax_uses_tfnotify_only(self):
        js = Path('static/js/cart_ajax.js').read_text(encoding='utf-8')
        self.assertIn('tfNotify', js)
        self.assertNotIn('tf-cart-snackbar', js)

    def test_carrito_page_has_no_qty_toast(self):
        js = Path('static/js/carrito_page.js').read_text(encoding='utf-8')
        self.assertNotIn('tfNotify', js)

    def test_django_messages_payload_when_flashed(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'nobody', 'password': 'wrong'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TF_FLASH_MESSAGES')
        self.assertContains(response, 'tf-flash-stack--noscript')
