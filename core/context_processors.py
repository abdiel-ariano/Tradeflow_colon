"""
Context processors globales para plantillas TradeFlow Colón.
"""


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
