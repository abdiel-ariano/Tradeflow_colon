"""Looped WebM background for the original login wave image."""
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
    """Ensure login wave uses local WebM video with static PNG fallback."""

    def setUp(self):
        self.client = Client()

    def test_login_template_uses_video_with_original_poster_and_fallback(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('login-page', body)
        self.assertIn('login-wave-video', body)
        self.assertIn('login-wave-static-fallback', body)
        self.assertIn('login-card', body)
        self.assertIn('images/login-figma/bg-wave.png', body)
        self.assertIn('images/login-figma/login-wave.webm', body)
        self.assertIn('autoplay', body)
        self.assertIn('muted', body)
        self.assertIn('loop', body)
        self.assertIn('playsinline', body)
        self.assertIn('poster=', body)
        self.assertNotIn('feTurbulence', body)
        self.assertNotIn('feDisplacementMap', body)
        self.assertNotIn('login-wave-animation', body)
        self.assertNotIn('login-wave-distortion.js', body)

    def test_login_css_uses_video_layer_without_image_transform(self):
        css_path = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'login.css'
        css = css_path.read_text(encoding='utf-8')
        self.assertIn('.login-wave-video', css)
        self.assertIn('.login-wave-static-fallback', css)
        self.assertNotIn('.login-wave-animation', css)
        self.assertNotIn('tradeflow-login-wave', css)
        self.assertNotIn('login-animated-background', css)
        self.assertNotIn('hue-rotate', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('.login-page', css)
        self.assertIn('overflow: hidden', css)

    def test_generator_enforces_visible_motion_threshold(self):
        script_path = Path(__file__).resolve().parents[2] / 'scripts' / 'generate_login_wave_video.py'
        script = script_path.read_text(encoding='utf-8')
        self.assertIn('MINIMUM_VISIBLE_DIFFERENCE', script)
        self.assertIn('cv2.remap', script)
        self.assertIn('astype(np.float32)', script)
        self.assertIn('load_original_on_white', script)

    def test_login_wave_webm_asset_exists(self):
        webm_path = Path(__file__).resolve().parents[2] / 'static' / 'images' / 'login-figma' / 'login-wave.webm'
        self.assertTrue(webm_path.exists())
        size = webm_path.stat().st_size
        self.assertGreater(size, 10_000)
        self.assertLess(size, 4 * 1024 * 1024)

    def test_password_toggle_still_present_on_login(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'data-target="id_password"')
        self.assertContains(response, 'auth-password-toggle.js')
