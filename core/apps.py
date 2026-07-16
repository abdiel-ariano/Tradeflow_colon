"""Django AppConfig for the TradeFlow Colón core application.

Wires post-migrate demo seeding, enterprise/cache signal modules, and
startup warnings for email and media storage misconfiguration.
"""
import logging
import sys

from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate

log = logging.getLogger(__name__)


def _maybe_seed_demo(sender, **kwargs):
    """Seed demo catalog after migrate when the product table is empty."""
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
        call_command('seed_catalog_images', limit=0)
    except Exception as exc:
        log.exception('cargar_demo falló: %s', exc)


class CoreConfig(AppConfig):
    """Register core signals and optional empty-DB demo seeding."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'TradeFlow Core'

    def ready(self):
        """Connect seed hook and import side-effect signal modules."""
        post_migrate.connect(_maybe_seed_demo, dispatch_uid='tradeflow_core_seed_demo_if_empty')
        from . import signals_enterprise  # noqa: F401
        from . import signals_cache  # noqa: F401
        self._log_platform_warnings()

    @staticmethod
    def _log_platform_warnings():
        """Warn on missing email infra or local-only media in production."""
        if 'runserver' not in sys.argv and 'migrate' not in sys.argv:
            return
        if 'test' in sys.argv or 'pytest' in sys.modules:
            return
        try:
            from django.conf import settings
            from core.utils.email_delivery import validate_email_infrastructure

            for msg in validate_email_infrastructure():
                log.warning('TradeFlow email: %s', msg)
            if not settings.DEBUG and 'FileSystemStorage' in settings.STORAGES.get(
                'default', {},
            ).get('BACKEND', ''):
                log.warning(
                    'TradeFlow storage: media en disco local; configure SUPABASE_URL + '
                    'SUPABASE_SERVICE_KEY para persistencia cloud.',
                )
        except Exception as exc:
            log.debug('platform warnings skipped: %s', exc)
