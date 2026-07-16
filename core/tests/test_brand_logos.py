"""Static brand wordmark assets for light and dark chrome.

Nav and hero must ship distinct white vs dark PNGs so TradeFlow Colón
remains legible on both marketplace backgrounds.
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class BrandLogoAssetTests(SimpleTestCase):
    """Verify packaged wordmark files are not identical copies."""

    def _md5(self, name: str) -> str:
        """Return the MD5 hex digest of a static/img asset."""
        path = Path(settings.BASE_DIR) / 'static' / 'img' / name
        return hashlib.md5(path.read_bytes()).hexdigest()

    def test_wordmark_white_differs_from_dark(self):
        """White and dark wordmark PNGs must be different files."""
        white = self._md5('logo-wordmark-white.png')
        dark = self._md5('logo-wordmark-dark.png')
        self.assertNotEqual(white, dark)
