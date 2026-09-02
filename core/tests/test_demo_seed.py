"""Pruebas de semilla demo sin contraseñas en código."""
from __future__ import annotations

import os
from unittest.mock import patch

from django.test import SimpleTestCase

from core.utils.demo_seed import demo_user_password


class DemoSeedPasswordTests(SimpleTestCase):
    """Valida que la clave demo provenga del entorno o se genere localmente."""

    def test_uses_configured_password(self):
        """Respeta DEMO_USER_PASSWORD cuando está definida."""
        with patch.dict(os.environ, {'DEMO_USER_PASSWORD': 'local-only-secret'}, clear=False):
            self.assertEqual(demo_user_password(), 'local-only-secret')

    def test_generates_password_when_missing(self):
        """Genera una clave aleatoria si no hay variable de entorno."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('DEMO_USER_PASSWORD', None)
            generated = demo_user_password()
            self.assertGreaterEqual(len(generated), 12)
