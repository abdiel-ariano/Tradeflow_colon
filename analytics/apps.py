"""Django app config for TradeFlow Analytics IA (DataFlow).

Registers the seller analytics package used by Mi Tienda and the
staff multi-source dashboard under Colon Free Zone marketplace ops.
"""
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """AppConfig for seller analytics and forecast surfaces.

    Labels the app in Django admin as Analytics IA (DataFlow) so
    staff can distinguish it from core CFZ catalog models.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"
    verbose_name = "Analytics IA (DataFlow)"
