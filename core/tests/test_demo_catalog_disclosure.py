"""Regression tests for transparent demonstration-catalog behavior."""
from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.context_processors import demo_catalog_context


class DemoCatalogDisclosureTests(SimpleTestCase):
    """Protect the disclosure flag, public copy, and assistant export."""

    def setUp(self):
        """Create a request without requiring database-backed middleware."""
        self.request = RequestFactory().get('/')

    @override_settings(DEMO_CATALOG_DISCLOSURE=True)
    def test_context_exposes_enabled_disclosure(self):
        """Return a strict boolean when the disclosure setting is enabled."""
        context = demo_catalog_context(self.request)

        self.assertIs(context['demo_catalog_enabled'], True)

    @override_settings(DEMO_CATALOG_DISCLOSURE=False)
    def test_context_exposes_disabled_disclosure(self):
        """Return a strict boolean when production data is declared real."""
        context = demo_catalog_context(self.request)

        self.assertIs(context['demo_catalog_enabled'], False)

    def test_base_template_contains_persistent_demo_notice(self):
        """Keep the bilingual simulated-data notice in the shared shell."""
        source = self._read_project_file('templates/core/base.html')

        self.assertIn('tf-demo-notice', source)
        self.assertIn('Catálogo de demostración.', source)
        self.assertIn('Demonstration catalog.', source)

    def test_catalog_card_does_not_claim_demo_supplier_is_verified(self):
        """Render demo-specific supplier and popularity labels conditionally."""
        source = self._read_project_file(
            'templates/core/includes/catalogo_card.html'
        )

        self.assertIn('Proveedor demo', source)
        self.assertIn('Demo supplier', source)
        self.assertIn('Popularidad simulada', source)

    def test_assistant_api_is_exported_on_browser_window(self):
        """Avoid the browser global-object regression."""
        source = self._read_project_file('templates/core/base.html')

        self.assertIn('window.TF_OPEN_ASSISTANT', source)
        self.assertNotIn('global.TF_OPEN_ASSISTANT', source)

    @staticmethod
    def _read_project_file(relative_path):
        """Read one UTF-8 project file using a repository-relative path."""
        path = Path(settings.BASE_DIR) / relative_path
        return path.read_text(encoding='utf-8')

