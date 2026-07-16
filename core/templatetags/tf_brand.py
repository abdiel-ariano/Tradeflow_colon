"""Brand helpers for deterministic company avatar colors.

Storefront cards without logos still need a stable accent so the same
CFZ seller always renders the same avatar background.
"""
from django import template

register = template.Library()

# Deterministic palette — same company always gets the same avatar color.
AVATAR_COLORS = (
    '#0F2A44',
    '#1B3B63',
    '#2E5B8A',
    '#0057A8',
    '#1A7A4A',
    '#F26522',
)


@register.filter
def company_avatar_color(company) -> str:
    """Pick a stable accent hex from company primary key."""
    if not company or not getattr(company, 'pk', None):
        return AVATAR_COLORS[0]
    return AVATAR_COLORS[company.pk % len(AVATAR_COLORS)]
