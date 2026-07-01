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


def category_icon_name(name: str | None) -> str:
    """Material Symbols icon for a category (header dropdown)."""
    if not name:
        return 'category'
    key = name.strip().lower()
    if any(k in key for k in ('elect', 'tech', 'device', 'computer')):
        return 'devices'
    if any(k in key for k in ('textil', 'cloth', 'apparel', 'fashion')):
        return 'checkroom'
    if any(k in key for k in ('food', 'grocery', 'beverage')):
        return 'restaurant'
    if any(k in key for k in ('logistic', 'ship', 'freight', 'transport')):
        return 'local_shipping'
    if any(k in key for k in ('beauty', 'cosmetic', 'perfum')):
        return 'spa'
    if any(k in key for k in ('home', 'furniture', 'garden')):
        return 'chair'
    if any(k in key for k in ('industrial', 'machine', 'tool')):
        return 'precision_manufacturing'
    if any(k in key for k in ('jewel', 'watch', 'optic')):
        return 'diamond'
    if any(k in key for k in ('auto', 'motor', 'spare')):
        return 'directions_car'
    if any(k in key for k in ('health', 'medical', 'pharma')):
        return 'medical_services'
    return 'category'
