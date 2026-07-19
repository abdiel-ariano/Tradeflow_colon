"""CSP must allow OAuth IdP redirects after allauth confirmation POST."""
from __future__ import annotations

from django.test import Client, TestCase, override_settings


@override_settings(
    DEBUG=True,
    ALLOWED_HOSTS=['localhost', 'testserver', '*'],
    SOCIAL_AUTH_ENABLED=True,
    SOCIALACCOUNT_LOGIN_ON_GET=False,
    SOCIALACCOUNT_PROVIDERS={
        'google': {
            'APP': {
                'client_id': 'test-google-id',
                'secret': 'test-google-secret',
                'key': '',
            },
        },
    },
)
class OAuthCspFormActionTests(TestCase):
    """Browsers apply form-action to the OAuth 302 redirect chain."""

    def setUp(self):
        self.client = Client(HTTP_HOST='localhost')

    def test_google_login_csp_allows_accounts_google(self):
        """Google confirmation page CSP includes accounts.google.com."""
        resp = self.client.get('/accounts/google/login/')
        self.assertEqual(resp.status_code, 200)
        csp = resp.get('Content-Security-Policy', '')
        self.assertIn("form-action 'self'", csp)
        self.assertIn('https://accounts.google.com', csp)
        self.assertIn('https://login.microsoftonline.com', csp)
        self.assertIn('https://www.linkedin.com', csp)

    def test_google_login_post_redirects_to_google(self):
        """Confirmation POST still returns a Google authorize redirect."""
        get_resp = self.client.get('/accounts/google/login/')
        self.assertEqual(get_resp.status_code, 200)
        post_resp = self.client.post('/accounts/google/login/')
        self.assertEqual(post_resp.status_code, 302)
        self.assertTrue(
            post_resp['Location'].startswith('https://accounts.google.com/'),
            post_resp['Location'],
        )
