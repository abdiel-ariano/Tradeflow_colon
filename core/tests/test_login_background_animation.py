"""Distortion animation for the original login wave image."""
from __future__ import annotations

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
class LoginBackgroundAnimationTests(TestCase):
    """Ensure login wave keeps original colors and uses SVG displacement."""

    def setUp(self):
        self.client = Client()

    def test_login_template_uses_original_image_with_svg_distortion(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('login-page', body)
        self.assertIn('login-wave-animation', body)
        self.assertIn('login-wave-fallback', body)
        self.assertIn('login-card', body)
        self.assertIn('images/login-figma/bg-wave.png', body)
        self.assertIn('tradeflow-wave-distortion', body)
        self.assertIn('tradeflow-wave-noise', body)
        self.assertIn('tradeflow-wave-displacement', body)
        self.assertIn('login-wave-distortion.js', body)
        self.assertNotIn('login-wave.svg', body)
        self.assertNotIn('grad-blue-violet', body)
        self.assertNotIn('login-animated-background', body)

    def test_login_css_keeps_fixed_container_without_image_transform(self):
        css_path = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'login.css'
        css = css_path.read_text(encoding='utf-8')
        self.assertIn('.login-wave-animation', css)
        self.assertIn('.login-wave-fallback', css)
        self.assertNotIn('tradeflow-login-wave', css)
        self.assertNotIn('login-animated-background', css)
        self.assertNotIn('hue-rotate', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('.login-page', css)
        self.assertIn('overflow: hidden', css)

    def test_distortion_script_only_animates_filter_attributes(self):
        js_path = Path(__file__).resolve().parents[2] / 'static' / 'js' / 'login-wave-distortion.js'
        js = js_path.read_text(encoding='utf-8')
        self.assertIn('baseFrequency', js)
        self.assertIn('scale', js)
        self.assertIn('prefers-reduced-motion', js)
        self.assertIn('requestAnimationFrame', js)
        self.assertNotIn('translate3d', js)
        self.assertNotIn('translateX', js)
        self.assertNotIn('style.transform', js)

    def test_password_toggle_still_present_on_login(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'data-target="id_password"')
        self.assertContains(response, 'auth-password-toggle.js')
