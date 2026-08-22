"""Regression tests for the public assistant left→right scroll dock."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class AssistantScrollDockTests(SimpleTestCase):
    """Keep the FAB left by default and glide right after scroll."""

    def test_base_template_docks_left_then_right_on_scroll(self):
        source = self._read('templates/core/base.html')
        self.assertIn('id="tf-assistant"', source)
        self.assertIn('width: fit-content', source)
        self.assertIn('tf-assistant--right', source)
        self.assertIn('TF_DOCK_SCROLL_Y', source)
        self.assertIn('window.TF_SYNC_ASSISTANT_DOCK', source)
        self.assertIn('setChatOpen', source)

    def test_notifications_does_not_steal_chat_handlers(self):
        source = self._read('static/js/tf_notifications.js')
        self.assertNotIn('patchChatWidget', source)
        self.assertNotIn('stopImmediatePropagation', source)
        self.assertIn('polishChatWidgetIcons', source)

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
