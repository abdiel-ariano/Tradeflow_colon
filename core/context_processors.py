"""
Context processors: carrito, i18n JS y Supabase público.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext as _


def cart_badge(request):
    """Conteo del carrito en navbar (solo compradores)."""
    if not request.user.is_authenticated:
        return {'carrito_count': 0}
    try:
        role = request.user.profile.role
    except Exception:
        role = None
    if request.user.is_superuser or role == 'admin' or role != 'buyer':
        return {'carrito_count': 0}
    carrito = request.session.get('carrito', {})
    count = sum(int(item.get('cantidad', 0) or 0) for item in carrito.values())
    return {'carrito_count': count}


def tf_i18n(request):
    """Cadenas i18n para scripts (TF_I18N)."""
    payload = {
        'close': _('Cerrar'),
        'cartTitle': _('Carrito'),
        'slide': _('Diapositiva'),
        'addedToCart': _('Producto agregado al carrito'),
        'cartAddedShort': _('Agregado al carrito'),
        'cartError': _('No se pudo agregar al carrito'),
        'networkError': _('Error de conexión'),
        'orders': _('Órdenes'),
        'products': _('Productos'),
        'companies': _('Empresas'),
        'emptySection': _('Sin productos en esta sección por ahora.'),
        'chartOrders': _('Órdenes'),
        'chartUsd': _('USD'),
        'chartPending': _('Pendiente'),
        'chartPaid': _('Pagado'),
        'chartShipped': _('Enviado'),
        'chartDelivered': _('Entregado'),
        'chartCancelled': _('Cancelado'),
        'chartLoadError': _('No se pudo cargar Chart.js. Recarga la página.'),
        'chartDataError': _('Datos de gráficos incompletos.'),
        'chartUpdateError': _('No se pudieron actualizar los gráficos.'),
        'chartInitError': _('No se pudieron inicializar los gráficos.'),
        'csvDownloaded': _('Archivo CSV descargado correctamente.'),
        'geoConfirmed': _('Ubicación confirmada.'),
        'geoDenied': _('Permiso de ubicación denegado.'),
        'geoUnsupported': _('Tu navegador no soporta geolocalización.'),
        'awaitingSeller': _('Esperando confirmación de empresa'),
        'orderUpdated': _('Estado de orden actualizado'),
    }
    return {'tf_i18n': payload}


def enterprise_saas(request):
    """Plan SaaS, uso mensual y créditos ads para portal seller."""
    import logging

    log = logging.getLogger('tradeflow.saas')

    if not request.user.is_authenticated:
        return {}
    try:
        role = request.user.profile.role
    except Exception:
        return {}
    if role not in ('seller', 'admin') and not request.user.is_superuser:
        return {}
    from core.models import Company

    company = Company.objects.filter(owner=request.user).first()
    if not company:
        return {'saas_snapshot': None}
    try:
        from core.utils.saas_billing import subscription_usage_snapshot

        snap = subscription_usage_snapshot(company)
        return {'saas_snapshot': snap, 'saas_company': company}
    except Exception as exc:
        log.warning(
            'enterprise_saas_context_failed user_id=%s company_id=%s: %s',
            request.user.pk,
            company.pk,
            exc,
            exc_info=True,
        )
        return {'saas_snapshot': None, 'saas_company': company}


def supabase_public(request):
    """Claves públicas Supabase para Realtime en frontend."""
    url = getattr(settings, 'SUPABASE_URL', '') or ''
    anon = getattr(settings, 'SUPABASE_ANON_KEY', '') or ''
    return {
        'SUPABASE_PUBLIC_URL': url,
        'SUPABASE_ANON_KEY': anon,
        'SUPABASE_REALTIME_ENABLED': bool(url and anon),
    }
