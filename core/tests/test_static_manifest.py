"""Manifest static storage content-hash URLs for login CSS.

Production WhiteNoise must fingerprint login.css so CFZ auth
pages bust caches without query-string version hacks.
"""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings


MANIFEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}


@override_settings(DEBUG=False, STORAGES=MANIFEST_STORAGES)
class LoginCssManifestTest(SimpleTestCase):
    """Assert hashed login.css URLs from storage and templates."""

    def test_login_css_url_has_content_hash_in_filename(self):
        """Return a hashed login.*.css path, not the bare static URL."""
        url = staticfiles_storage.url('css/login.css')
        self.assertIn('login.', url)
        self.assertTrue(url.endswith('.css'), url)
        self.assertNotEqual(url, '/static/css/login.css')

    def test_login_template_uses_manifest_static_url(self):
        """Render {% static %} without legacy version query markers."""
        rendered = Template(
            '{% load static %}'
            '<link rel="stylesheet" href="{% static \'css/login.css\' %}">'
        ).render(Context())
        self.assertIn('login.', rendered)
        self.assertNotIn('-login14', rendered)
        self.assertNotIn('tf_asset_version', rendered)
