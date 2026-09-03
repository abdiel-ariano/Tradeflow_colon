"""Regression tests for the public assistant left→right scroll dock."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings


class AssistantScrollDockTests(SimpleTestCase):
    """Keep the FAB left by default and glide right after scroll."""

    def test_base_template_uses_full_width_rail_dock(self):
        source = self._read('templates/core/base.html')
        self.assertIn('id="tf-assistant-rail"', source)
        self.assertIn('data-tf-dock="left"', source)
        self.assertIn('tf-assistant-rail', source)
        self.assertIn('TF_DOCK_SCROLL_Y', source)
        self.assertIn('applyAssistantDock', source)
        self.assertIn('translate3d(', source)
        self.assertIn('.cat-results-scroll', source)
        self.assertIn("document.addEventListener(", source)
        self.assertIn("{ passive: true, capture: true }", source)
        self.assertIn('window.TF_SYNC_ASSISTANT_DOCK', source)
        self.assertIn('setChatOpen', source)
        self.assertIn('is-chat-open', source)
        self.assertIn('tf-assistant--open', source)
        self.assertIn('assistant.offsetWidth', source)
        # Must not pin the FAB with position:fixed on the right by default.
        self.assertNotRegex(
            source,
            r'#tf-assistant\s*\{[^}]*right:\s*max\([^}]*\)\s*!important',
        )

    def test_open_chat_panel_is_in_flow_not_clipped_by_rail(self):
        """FAB click must reveal the panel; overflow:hidden on the rail
        used to clip the absolutely positioned window above the 56px dock.
        """
        source = self._read('templates/core/base.html')
        self.assertIn('#tf-assistant-rail.is-chat-open', source)
        self.assertIn('overflow: visible !important', source)
        self.assertIn(
            '#tf-assistant-rail #tf-assistant.tf-assistant--open',
            source,
        )
        self.assertIn('order: -1', source)
        self.assertRegex(
            source,
            r'#tf-assistant-rail #tf-chat-window\s*\{[^}]*position:\s*relative',
        )
        self.assertNotRegex(
            source,
            r'#tf-assistant-rail #tf-chat-window\s*\{[^}]*position:\s*absolute',
        )
        self.assertNotRegex(
            source,
            r'#tf-assistant-rail #tf-chat-window\s*\{[^}]*bottom:\s*calc\(100%',
        )

    def test_notifications_does_not_steal_chat_handlers(self):
        source = self._read('static/js/tf_notifications.js')
        self.assertNotIn('patchChatWidget', source)
        self.assertNotIn('stopImmediatePropagation', source)
        self.assertNotIn('tf-chat-toggle', source)

    def test_design_system_does_not_pin_toggle_to_viewport_right(self):
        source = self._read('static/css/tf-design-system.css')
        self.assertIn('#tf-assistant #tf-chat-toggle', source)
        self.assertNotRegex(
            source,
            r'(?s)#tf-chat-toggle\s*\{[^}]*position:\s*fixed[^}]*right:\s*24px',
        )

    @staticmethod
    def _read(relative_path: str) -> str:
        path = Path(settings.BASE_DIR) / relative_path
        return path.read_text(encoding='utf-8')


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class AssistantLauncherRenderTests(TestCase):
    """Public pages must ship the assistant FAB and open wiring."""

    def test_home_renders_assistant_launcher(self):
        """Public home includes the assistant FAB wired to setChatOpen."""
        response = Client().get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="tf-chat-toggle"', html)
        self.assertIn('id="tf-chat-window"', html)
        self.assertIn('function setChatOpen', html)
        self.assertIn('is-chat-open', html)
        self.assertIn('tf-assistant--open', html)
