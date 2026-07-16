"""Invalidate merchandising cache when catalog or order data changes.

Home promo sections, nav categories, and related cached fragments must
stay coherent with Product, Company, Category, and Order mutations.
"""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.models import Category, Company, HomePromoSection, Order, Product


def _bust_merchandising_cache(**kwargs):
    """Clear shared merchandising cache keys."""
    from core.utils.tradeflow_cache import invalidate_merchandising_cache

    invalidate_merchandising_cache()


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def bust_cache_on_product(sender, **kwargs):
    """Bust merchandising cache after product create/update/delete."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Company)
@receiver(post_delete, sender=Company)
def bust_cache_on_company(sender, **kwargs):
    """Bust merchandising cache after company create/update/delete."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def bust_cache_on_category(sender, **kwargs):
    """Bust merchandising cache after category create/update/delete."""
    _bust_merchandising_cache()


@receiver(post_save, sender=HomePromoSection)
@receiver(post_delete, sender=HomePromoSection)
def bust_cache_on_home_promo(sender, **kwargs):
    """Bust merchandising cache after home promo section changes."""
    _bust_merchandising_cache()


@receiver(m2m_changed, sender=HomePromoSection.products.through)
@receiver(m2m_changed, sender=HomePromoSection.companies.through)
@receiver(m2m_changed, sender=HomePromoSection.categories.through)
def bust_cache_on_home_promo_m2m(sender, **kwargs):
    """Bust merchandising cache when promo M2M membership changes."""
    _bust_merchandising_cache()


@receiver(post_save, sender=Order)
def bust_cache_on_order(sender, instance, **kwargs):
    """Bust cache when order status may affect merchandising surfaces."""
    if kwargs.get('update_fields') and 'status' not in kwargs['update_fields']:
        return
    _bust_merchandising_cache()
