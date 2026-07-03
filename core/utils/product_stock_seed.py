"""Realistic inventory quantities for demo / enterprise seed data."""
from __future__ import annotations

import random


def realistic_stock_qty(rng: random.Random, *, tier: int = 2) -> int:
    """
  Mix low (3–15), medium (50–300), and high (1000+) stock levels.

  Tier-1 suppliers skew slightly toward higher availability.
    """
    roll = rng.random()
    if roll < 0.18:
        return rng.randint(3, 15)
    if roll < 0.58:
        return rng.randint(50, 300)
    if roll < 0.82:
        return rng.randint(301, 950)
    base = rng.randint(1000, 4200)
    return base + (rng.randint(200, 800) if tier == 1 else 0)
