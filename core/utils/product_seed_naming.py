"""Credible B2B product titles for enterprise seed data.

Composes supplier brand, model code, and technical spec so demo
catalogs read like real ZLC wholesale listings.
"""
from __future__ import annotations

import random
import re

_LOT_SUFFIX_RE = re.compile(r'\s*[—–\-]\s*lot\s+\d+\s*$', re.IGNORECASE)

_MODEL_SUFFIXES = ('100', '200', '300', 'Pro', 'Plus', 'Elite', 'X', 'G2', 'CFZ')


def strip_lot_suffix(name: str) -> str:
    """Remove legacy ``— lot NNN`` suffix from seeded product names."""
    return _LOT_SUFFIX_RE.sub('', (name or '').strip()).strip()


def _brand_from_company(company_name: str) -> str:
    """Return first meaningful token of the supplier name (stable per company)."""
    cleaned = re.sub(r'\b(S\.A\.|Ltda\.|Inc\.|Group|Wholesale|Imports|B2B)\b', '', company_name, flags=re.I)
    parts = [p for p in re.split(r'[\s,&]+', cleaned.strip()) if p]
    if not parts:
        return 'CFZ'
    brand = parts[0]
    if len(brand) <= 2 and len(parts) > 1:
        brand = parts[1]
    return brand[:24]


def build_seed_product_name(
    *,
    company_name: str,
    base_title: str,
    description: str,
    product_index: int,
    rng: random.Random,
) -> str:
    """Compose supplier brand + model code + technical spec (no lot suffix)."""
    brand = _brand_from_company(company_name)
    model = f'{rng.choice(_MODEL_SUFFIXES)}{rng.randint(10, 99)}'
    spec = (description or '').split('.')[0].strip()
    title = strip_lot_suffix(base_title)
    if spec and spec.lower() not in title.lower():
        return f'{brand} {model} {title} – {spec}'[:200]
    return f'{brand} {model} {title}'[:200]
