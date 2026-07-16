"""Realistic inventory quantities for demo and enterprise seed data.

Mixes low, medium, and high stock so CFZ dashboards show believable
alerts and bestsellers.
"""
from __future__ import annotations

import random


def realistic_stock_qty(rng: random.Random, *, tier: int = 2) -> int:
    """Sample low/medium/high stock quantities for believable CFZ demos."""
    roll = rng.random()
    if roll < 0.18:
        return rng.randint(3, 15)
    if roll < 0.58:
        return rng.randint(50, 300)
    if roll < 0.82:
        return rng.randint(301, 950)
    base = rng.randint(1000, 4200)
    return base + (rng.randint(200, 800) if tier == 1 else 0)
