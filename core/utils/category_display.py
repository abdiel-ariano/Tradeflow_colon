"""Etiquetas de categoría del catálogo según idioma (capa de UI).

Los datos semilla mezclan nombres en inglés y español; el marketplace debe
mostrar un solo idioma sin reescribir las filas ``Category`` almacenadas.
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
    """Devuelve la etiqueta de categoría para el locale; si no, el nombre guardado."""
    if not name:
        return ''
    lang_code = (lang or get_language() or settings.LANGUAGE_CODE)[:2]
    if lang_code == 'es':
        return _CATEGORY_LABEL_ES.get(name.strip(), name)
    key = name.strip().lower()
    return _CATEGORY_LABEL_EN.get(key, name)


def category_icon_name(name: str | None) -> str:
    """Devuelve el nombre de icono Material Symbols para el menú de categoría."""
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
