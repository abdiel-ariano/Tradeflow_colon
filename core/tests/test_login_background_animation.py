"""Animated multicolor background on the TradeFlow login page."""
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
    """Ensure login background uses CSS-only wave animation hooks."""

    def setUp(self):
        self.client = Client()

    def test_login_template_exposes_animation_classes(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('login-page', body)
        self.assertIn('login-animated-background', body)
        self.assertIn('login-card', body)
        self.assertIn('images/login-figma/bg-wave.png', body)

    def test_login_css_defines_wave_keyframes_and_reduced_motion(self):
        css_path = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'login.css'
        css = css_path.read_text(encoding='utf-8')
        self.assertIn('.login-animated-background', css)
        self.assertIn('@keyframes tradeflow-login-wave', css)
        self.assertIn('animation: tradeflow-login-wave 20s ease-in-out infinite alternate', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('.login-page', css)
        self.assertIn('overflow: hidden', css)

    def test_password_toggle_still_present_on_login(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'data-target="id_password"')
        self.assertContains(response, 'auth-password-toggle.js')
