"""RFC 9116 security.txt and robots.txt for Cloudflare Security Insights."""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', 'tradeflowcolon.com'],
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    TRADEFLOW_CONTACT_EMAIL='tradeflowcolon@gmail.com',
)
class SecurityTxtAndRobotsTests(SimpleTestCase):
    """Assert disclosure file and AI-crawler robots policy."""

    def test_well_known_security_txt(self):
        """Serve RFC 9116 security.txt at /.well-known/security.txt."""
        resp = self.client.get('/.well-known/security.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/plain', resp['Content-Type'])
        body = resp.content.decode('utf-8')
        self.assertIn('Contact: mailto:security@tradeflow.pa', body)
        self.assertIn('Expires:', body)
        self.assertIn('Canonical: https://tradeflowcolon.com/.well-known/security.txt', body)
        self.assertIn('Preferred-Languages: es, en', body)

    def test_legacy_security_txt_alias(self):
        """Also expose /security.txt for older scanners."""
        resp = self.client.get('/security.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Contact: mailto:security@tradeflow.pa', resp.content.decode())

    def test_robots_txt_blocks_ai_bots(self):
        """robots.txt allows humans/search but Disallows common AI scrapers."""
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('User-agent: *', body)
        self.assertIn('Disallow: /admin/', body)
        self.assertIn('User-agent: GPTBot', body)
        self.assertIn('User-agent: Bytespider', body)
        self.assertIn('Disallow: /', body)
        self.assertIn('Sitemap: https://tradeflowcolon.com/sitemap.xml', body)
