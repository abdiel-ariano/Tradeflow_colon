"""Filesystem paths to official TradeFlow Colón logo PNGs.

PDF and email generators need absolute paths under ``static/img/``.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

STATIC_IMG_DIR = Path(settings.BASE_DIR) / "static" / "img"

LOGO_ICON_COLOR = "logo-icon-color.png"
LOGO_ICON_WHITE = "logo-icon-white.png"
LOGO_WORDMARK_WHITE = "logo-wordmark-white.png"


def logo_static_path(filename: str) -> Path:
    """Return absolute path to a brand PNG under ``static/img/``."""
    return STATIC_IMG_DIR / filename


def logo_icon_color_path() -> Path:
    """Return absolute path to the color icon logo PNG."""
    return logo_static_path(LOGO_ICON_COLOR)
