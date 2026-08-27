"""Animated SVG wave background on the TradeFlow login page."""
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
    """Ensure login background uses internal SVG gradient animation hooks."""

    def setUp(self):
        self.client = Client()

    def test_login_template_exposes_svg_wave_and_png_fallback(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('login-page', body)
        self.assertIn('login-wave-svg', body)
        self.assertIn('login-wave-fallback', body)
        self.assertIn('login-card', body)
        self.assertIn('images/login-figma/login-wave.svg', body)
        self.assertIn('images/login-figma/bg-wave.png', body)
        self.assertNotIn('login-animated-background', body)

    def test_login_css_uses_fixed_svg_container_and_reduced_motion(self):
        css_path = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'login.css'
        css = css_path.read_text(encoding='utf-8')
        self.assertIn('.login-wave-svg', css)
        self.assertIn('.login-wave-fallback', css)
        self.assertNotIn('tradeflow-login-wave', css)
        self.assertNotIn('login-animated-background', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('.login-page', css)
        self.assertIn('overflow: hidden', css)

    def test_login_wave_svg_animates_internal_gradients_only(self):
        svg_path = Path(__file__).resolve().parents[2] / 'static' / 'images' / 'login-figma' / 'login-wave.svg'
        svg = svg_path.read_text(encoding='utf-8')
        self.assertIn('wave-alpha-mask', svg)
        self.assertIn('bg-wave.png', svg)
        self.assertIn('grad-blue-violet', svg)
        self.assertIn('grad-red-fuchsia', svg)
        self.assertIn('animateTransform attributeName="gradientTransform"', svg)
        self.assertIn('dur="18s"', svg)
        self.assertIn('dur="22s"', svg)
        self.assertIn('dur="26s"', svg)
        self.assertIn('dur="30s"', svg)
        self.assertIn('feTurbulence', svg)
        self.assertNotIn('translate3d', svg)

    def test_password_toggle_still_present_on_login(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'data-target="id_password"')
        self.assertContains(response, 'auth-password-toggle.js')
