"""
=============================================================================
TRADEFLOW COLÓN — core/apps.py
=============================================================================
Configuración de la aplicación 'core'.
Opcional: sembrado automático de datos demo tras migrate si la BD está vacía.
=============================================================================
"""
import logging
import sys

from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate

log = logging.getLogger(__name__)


def _maybe_seed_demo(sender, **kwargs):
    """
    Tras migraciones de core, si SEED_DEMO_IF_EMPTY está activo y no hay
    productos, ejecuta cargar_demo para tener catálogo y usuarios de prueba.
    """
    if kwargs.get('raw'):
        return
    if sender.name != 'core':
        return
    if 'test' in sys.argv or 'pytest' in sys.modules:
        return
    from django.conf import settings

    if not getattr(settings, 'SEED_DEMO_IF_EMPTY', False):
        return
    try:
        from core.models import Product

        if Product.objects.exists():
            return
    except Exception as exc:
        log.warning('SEED_DEMO_IF_EMPTY omitido (BD no lista): %s', exc)
        return
    log.info('SEED_DEMO_IF_EMPTY: catálogo vacío, ejecutando cargar_demo…')
    try:
        call_command('cargar_demo')
    except Exception as exc:
        log.exception('cargar_demo falló: %s', exc)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'TradeFlow Core'

    def ready(self):
        post_migrate.connect(_maybe_seed_demo, dispatch_uid='tradeflow_core_seed_demo_if_empty')
        from . import signals_enterprise  # noqa: F401
