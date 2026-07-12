"""Invalida cache de merchandising cuando cambia el catálogo o pedidos."""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.models import Category, Company, HomePromoSection, Order, Product


def _bust_merchandising_cache(**kwargs):
    from core.utils.tradeflow_cache import invalidate_merchandising_cache

    invalidate_merchandising_cache()


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def bust_cache_on_product(sender, **kwargs):
    """Bust cache on product."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Company)
@receiver(post_delete, sender=Company)
def bust_cache_on_company(sender, **kwargs):
    """Bust cache on company."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def bust_cache_on_category(sender, **kwargs):
    """Bust cache on category."""
    _bust_merchandising_cache()


@receiver(post_save, sender=HomePromoSection)
@receiver(post_delete, sender=HomePromoSection)
def bust_cache_on_home_promo(sender, **kwargs):
    """Bust cache on home promo."""
    _bust_merchandising_cache()


@receiver(m2m_changed, sender=HomePromoSection.products.through)
@receiver(m2m_changed, sender=HomePromoSection.companies.through)
@receiver(m2m_changed, sender=HomePromoSection.categories.through)
def bust_cache_on_home_promo_m2m(sender, **kwargs):
    """Bust cache on home promo m2m."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Order)
def bust_cache_on_order(sender, instance, **kwargs):
    """Bust cache on order."""
    if kwargs.get('update_fields') and 'status' not in kwargs['update_fields']:
        return
    _bust_merchandising_cache()
