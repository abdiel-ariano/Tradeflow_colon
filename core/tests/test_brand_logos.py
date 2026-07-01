"""Brand logo assets — wordmark white vs dark must differ."""
import hashlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class BrandLogoAssetTests(SimpleTestCase):
    def _md5(self, name: str) -> str:
        path = Path(settings.BASE_DIR) / 'static' / 'img' / name
        return hashlib.md5(path.read_bytes()).hexdigest()

    def test_wordmark_white_differs_from_dark(self):
        white = self._md5('logo-wordmark-white.png')
        dark = self._md5('logo-wordmark-dark.png')
        self.assertNotEqual(white, dark)
