"""Pruebas de documentación del repositorio."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DocumentationInventoryTests(SimpleTestCase):
    """Comprueba que la documentación canónica en español exista."""

    def test_spanish_doc_index_and_guides_exist(self):
        """El índice y las guías principales están en docs/."""
        docs = settings.BASE_DIR / 'docs'
        required = [
            'README.md',
            'DOCUMENTACION_TECNICA.md',
            'CALIDAD_CODIGO.md',
            'CORREO_TRANSACCIONAL.md',
            'BASE_DE_DATOS.md',
            'INTERNACIONALIZACION.md',
            'INVENTARIO_MODULOS.md',
        ]
        for name in required:
            with self.subTest(doc=name):
                path = docs / name
                self.assertTrue(path.is_file(), f'Falta {path}')
                content = path.read_text(encoding='utf-8')
                self.assertGreater(len(content), 200)

    def test_readme_points_to_resend_not_legacy_gmail_only(self):
        """README enlaza correo Resend y documentación técnica actual."""
        readme = (settings.BASE_DIR / 'README.md').read_text(encoding='utf-8')
        self.assertIn('CORREO_TRANSACCIONAL.md', readme)
        self.assertIn('DOCUMENTACION_TECNICA.md', readme)
        self.assertIn('Resend', readme)

    def test_deprecated_email_docs_warn_readers(self):
        """Las guías legacy advierten que están deprecadas."""
        enterprise = (
            settings.BASE_DIR / 'docs' / 'ENTERPRISE_EMAIL.md'
        ).read_text(encoding='utf-8')
        self.assertIn('deprecado', enterprise.lower())
        self.assertIn('CORREO_TRANSACCIONAL.md', enterprise)
