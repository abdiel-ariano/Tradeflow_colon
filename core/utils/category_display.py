"""English display labels for catalog categories (UI layer)."""
from __future__ import annotations

_CATEGORY_LABEL_EN = {
    'electrónica': 'Electronics',
    'electronica': 'Electronics',
    'electronics': 'Electronics',
    'textiles': 'Textiles',
    'perfumería y cosméticos': 'Perfumery & Cosmetics',
    'perfumeria y cosmeticos': 'Perfumery & Cosmetics',
}


def category_display_name(name: str | None) -> str:
    """Return English-facing category label; falls back to stored name."""
    if not name:
        return ''
    key = name.strip().lower()
    return _CATEGORY_LABEL_EN.get(key, name)
