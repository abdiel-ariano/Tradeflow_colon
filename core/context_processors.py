"""
=============================================================================
ACCIÓN: REEMPLAZAR
DESTINO: core/context_processors.py
=============================================================================
Context processors: carrito y cadenas i18n para JavaScript (TF_I18N).
=============================================================================
"""
import json

from django.utils.translation import gettext as _


def cart_badge(request):
    """
    Expone el conteo del carrito en todas las páginas (badge del navbar).

    Args:
        request: HttpRequest.

    Returns:
        dict: ``carrito_count`` (int).
    """
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
    """
    Expone ``TF_I18N`` como JSON seguro para scripts (carrusel, carrito, charts).

    Args:
        request: HttpRequest.

    Returns:
        dict: ``tf_i18n_json`` cadena JSON.
    """
    payload = {
        'close': _('Cerrar'),
        'cartTitle': _('Carrito'),
        'slide': _('Diapositiva'),
        'addedToCart': _('Producto agregado al carrito'),
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
        'chartDataError': _('Datos de gráficos incompletos. Recarga o cambia el período (7/30/90).'),
        'chartUpdateError': _('No se pudieron actualizar los gráficos.'),
        'chartInitError': _('No se pudieron inicializar los gráficos.'),
        'csvDownloaded': _('Archivo CSV descargado correctamente.'),
    }
    return {'tf_i18n': payload}
