"""Locale-aware display labels for catalog categories (UI layer).

Seed data mixes English and Spanish names; the marketplace must show
one language without rewriting stored Category rows.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import get_language

_CATEGORY_LABEL_EN = {
    'electrónica': 'Electronics',
    'electronica': 'Electronics',
    'electronics': 'Electronics',
    'textiles': 'Textiles',
    'perfumería y cosméticos': 'Perfumery & Cosmetics',
    'perfumeria y cosmeticos': 'Perfumery & Cosmetics',
}

_CATEGORY_LABEL_ES = {
    'Electronics & Office': 'Electrónica y oficina',
    'Textiles & Uniforms': 'Textiles y uniformes',
    'Accessories & Leather Goods': 'Accesorios y marroquinería',
    'Home & Appliances': 'Hogar y electrodomésticos',
    'Gaming & Peripherals': 'Gaming y periféricos',
    'Logistics & Packaging': 'Logística y empaque',
    'General Imports': 'Importaciones generales',
    'Electronics': 'Electrónica',
    'Textiles': 'Textiles',
    'Perfumery & Cosmetics': 'Perfumería y cosméticos',
}


def category_display_name(name: str | None, lang: str | None = None) -> str:
    """Return locale-facing category label; fall back to the stored name."""
    if not name:
        return ''
    lang_code = (lang or get_language() or settings.LANGUAGE_CODE)[:2]
    if lang_code == 'es':
        return _CATEGORY_LABEL_ES.get(name.strip(), name)
    key = name.strip().lower()
    return _CATEGORY_LABEL_EN.get(key, name)


def category_icon_name(name: str | None) -> str:
    """Return Material Symbols icon name for a category header dropdown."""
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
