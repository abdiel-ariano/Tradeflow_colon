"""Structured product detail content built only from existing product data."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.utils.translation import gettext as _

_BULLET_RE = re.compile(r'^[\-\u2022\*•]\s+')
_NUMBERED_RE = re.compile(r'^\d+[\.\)]\s+')


@dataclass
class ProductDescriptionSections:
    """Buyer-facing description blocks derived from stored product text."""

    overview_paragraphs: list[str] = field(default_factory=list)
    feature_items: list[str] = field(default_factory=list)
    has_content: bool = False


def _clean_line(value: str) -> str:
    return ' '.join((value or '').split()).strip()


def _sentence_features(paragraph: str) -> tuple[list[str], list[str]]:
    """Split a paragraph into an overview sentence and feature bullets."""
    text = _clean_line(paragraph)
    if not text:
        return [], []
    parts = [part.strip() for part in re.split(r'(?<=[.!?])\s+', text) if part.strip()]
    if len(parts) < 2:
        return [text], []
    return [parts[0]], parts[1:]


def parse_product_description_sections(description: str) -> ProductDescriptionSections:
    """Parse description text into overview and feature bullets when possible."""
    sections = ProductDescriptionSections()
    raw = (description or '').strip()
    if not raw:
        return sections

    overview: list[str] = []
    features: list[str] = []

    blocks = [block.strip() for block in re.split(r'\n\s*\n', raw) if block.strip()]
    if not blocks:
        blocks = [raw]

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        bullet_lines = [
            _BULLET_RE.sub('', line) if _BULLET_RE.match(line) else _NUMBERED_RE.sub('', line)
            for line in lines
            if _BULLET_RE.match(line) or _NUMBERED_RE.match(line)
        ]
        bullet_lines = [_clean_line(item) for item in bullet_lines if _clean_line(item)]

        if bullet_lines:
            features.extend(bullet_lines)
            prose_lines = [
                line for line in lines
                if not _BULLET_RE.match(line) and not _NUMBERED_RE.match(line)
            ]
            prose = _clean_line(' '.join(prose_lines))
            if prose:
                overview.append(prose)
            continue

        if len(lines) == 1:
            overview_part, sentence_features = _sentence_features(lines[0])
            if sentence_features:
                overview.extend(overview_part)
                features.extend(sentence_features)
            else:
                overview.append(_clean_line(lines[0]))
        else:
            overview.append(_clean_line(' '.join(lines)))

    sections.overview_paragraphs = overview
    sections.feature_items = features
    sections.has_content = bool(overview or features)
    return sections


def product_description_heading_overview() -> str:
    return _('Product overview')


def product_description_heading_features() -> str:
    return _('Key features')


def product_description_heading_applications() -> str:
    return _('Applications')


def product_description_heading_trade() -> str:
    return _('Trade information')
