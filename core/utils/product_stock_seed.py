"""Cantidades de inventario realistas para datos demo y semilla enterprise.

Mezcla stock bajo, medio y alto para que los dashboards ZLC muestren alertas
y bestsellers creíbles.
"""
from __future__ import annotations

import random


def realistic_stock_qty(rng: random.Random, *, tier: int = 2) -> int:
    """Muestrea cantidades de stock bajo/medio/alto para demos ZLC creíbles."""
    roll = rng.random()
    if roll < 0.18:
        return rng.randint(3, 15)
    if roll < 0.58:
        return rng.randint(50, 300)
    if roll < 0.82:
        return rng.randint(301, 950)
    base = rng.randint(1000, 4200)
    return base + (rng.randint(200, 800) if tier == 1 else 0)
