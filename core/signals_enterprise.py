"""Refresh SaaS billing usage when seller orders change.

Order and OrderItem saves update monthly usage counters that gate
seller plan limits in the CFZ marketplace portal.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order, OrderItem


@receiver(post_save, sender=OrderItem)
def refresh_billing_on_order_item(sender, instance, **kwargs):
    """Recompute company billing usage after a non-cancelled line item save."""
    if instance.order.status == 'cancelled':
        return
    try:
        from core.utils.saas_billing import refresh_billing_usage

        refresh_billing_usage(instance.product.company)
    except Exception:
        pass


@receiver(post_save, sender=Order)
def refresh_billing_on_order_status(sender, instance, **kwargs):
    """Recompute usage for each seller company on the order."""
    if instance.status == 'cancelled':
        return
    try:
        from core.utils.saas_billing import refresh_billing_usage

        company_ids = (
            instance.items.values_list('product__company_id', flat=True).distinct()
        )
        from core.models import Company

        for cid in company_ids:
            if cid:
                refresh_billing_usage(Company.objects.get(pk=cid))
    except Exception:
        pass
