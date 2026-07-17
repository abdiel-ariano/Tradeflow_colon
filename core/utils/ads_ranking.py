"""Impulso de productos patrocinados sobre el merchandising del catálogo.

Los vendedores gastan créditos publicitarios del plan para elevar SKUs en
búsqueda y secciones del home sin reemplazar bestsellers orgánicos ni flags destacados.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, DecimalField, F, Value, When
from django.utils import timezone

from core.enterprise_models import AdCampaign, AdCreditAccount


def active_boost_map() -> dict[int, Decimal]:
    """Mapa product_id → peso de impulso de campaña activa para el ranking."""
    now = timezone.now()
    boosts = {}
    for row in (
        AdCampaign.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
        .exclude(product_id__isnull=True)
        .values('product_id', 'boost_weight')
    ):
        boosts[row['product_id']] = Decimal(str(row['boost_weight']))
    return boosts


def annotate_sponsored_score(queryset):
    """Eleva la puntuación del producto cuando una campaña activa lo apunta."""
    boosts = active_boost_map()
    if not boosts:
        return queryset.annotate(
            sponsored_score=F('merchandising_priority'),
        )
    whens = [When(pk=pid, then=Value(float(w))) for pid, w in boosts.items()]
    return queryset.annotate(
        boost_multiplier=Case(
            *whens,
            default=Value(1.0),
            output_field=DecimalField(max_digits=6, decimal_places=2),
        ),
        sponsored_score=F('merchandising_priority') * F('boost_multiplier'),
    )


def ensure_ad_credits(company, monthly_credits: int = 0):
    """Asegura que exista la billetera de créditos publicitarios con al menos ``amount``."""
    account, created = AdCreditAccount.objects.get_or_create(company=company)
    if created and monthly_credits:
        account.balance = monthly_credits
        account.save(update_fields=['balance'])
    return account
