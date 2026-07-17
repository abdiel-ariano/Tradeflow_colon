"""Controla compradores y vendedores con OTP de correo y solicitudes de acceso.

La navegación pública del catálogo ZLC permanece abierta; checkout, portal
vendedor y APIs enterprise exigen correo verificado y (para compradores)
aprobación cuando ``REQUIRE_APPROVED_APPLICATION`` está activo.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import UserApplication, UserProfile

# Paths always public (locale prefix already stripped)
PUBLIC_PATH_PREFIXES = (
    '/login',
    '/signup',
    '/signup/oauth/',
    '/logout',
    '/accounts/',
    '/solicitud-acceso',
    '/pending-approval',
    '/onboarding/',
    '/verificar/',
    '/verificar-email/',
    '/reenviar-verificacion',
    '/recuperar-clave',
    '/admin/',
    '/health/',
    '/i18n/',
    '/static/',
    '/media/',
    '/mapa/',
    '/visitante/',
    '/transportistas/aplicar',
    '/api/v1/health',
)

PROTECTED_PATH_PREFIXES = (
    '/checkout',
    '/mis-ordenes',
    '/cotizaciones',
    '/mi-tienda',
    '/dashboard',
    '/ordenes',
    '/productos',
    '/empresas',
    '/perfil',
    '/api/seller',
    '/api/v1/inventory',
    '/api/v1/pricing',
    '/api/productos',
    '/api/asistente',
    '/api/dashboard-stats',
)

# Purchase paths need login + verification; catalog/cart stay public.
BROWSE_PATH_PREFIXES = (
    '/',
    '/catalogo',
    '/tienda',
    '/carrito',
    '/api/home-merchandising',
)


def normalize_path(path: str) -> str:
    """Quita el prefijo de locale /en/ o /es/ para comparaciones de acceso."""
    p = path or '/'
    if p.startswith('/en/'):
        return p[3:] or '/'
    if p.startswith('/es/'):
        return p[3:] or '/'
    return p


def is_public_path(path: str) -> bool:
    """Devuelve True cuando la ruta no requiere auth ni puerta de solicitud."""
    p = normalize_path(path)
    if p in ('/', ''):
        return True
    return any(p == pref.rstrip('/') or p.startswith(pref) for pref in PUBLIC_PATH_PREFIXES)


def is_protected_path(path: str) -> bool:
    """Devuelve True para checkout, pedidos, APIs de vendedor y otras rutas restringidas."""
    p = normalize_path(path)
    return any(p.startswith(pref) for pref in PROTECTED_PATH_PREFIXES)


def user_is_platform_exempt(user) -> bool:
    """Devuelve True para anónimos, staff, superusuario o rol de perfil admin."""
    if not user or not user.is_authenticated:
        return True
    if user.is_superuser or user.is_staff:
        return True
    try:
        if user.profile.role == 'admin':
            return True
    except UserProfile.DoesNotExist:
        pass
    return False


def latest_application_for_email(email: str) -> UserApplication | None:
    """Devuelve el ``UserApplication`` más reciente para ``email``, si existe."""
    if not email:
        return None
    return (
        UserApplication.objects.filter(email__iexact=email.strip())
        .order_by('-created_at')
        .first()
    )


def application_gate_status(email: str, *, role: str | None = None) -> str | None:
    """Devuelve el código de puerta de solicitud, o None cuando el acceso está permitido."""
    if role == 'seller':
        return None
    if not getattr(settings, 'REQUIRE_APPROVED_APPLICATION', False):
        return None

    app = latest_application_for_email(email)
    if not app:
        if getattr(settings, 'ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION', False):
            return None
        return 'required'

    if app.status == 'approved':
        return None
    if app.status == 'rejected':
        return 'rejected'
    if app.status == 'pending':
        return 'pending'
    return 'pending'


def user_needs_role_completion(user) -> bool:
    """Devuelve True cuando falta el perfil o el rol no es comprador/vendedor."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return True
    return profile.role not in ('buyer', 'seller', 'admin')


def email_verification_required(user) -> bool:
    """Devuelve True cuando el usuario debe completar el OTP de correo antes de rutas operativas."""
    if not user or not user.is_authenticated or user_is_platform_exempt(user):
        return False
    if not (
        getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False)
        or getattr(settings, 'EXPO_DEMO_MODE', False)
    ):
        return False
    try:
        return not user.profile.email_verificado
    except UserProfile.DoesNotExist:
        return True


def is_protected_path(path: str) -> bool:
    """Devuelve True para checkout, pedidos, APIs de vendedor y otras rutas restringidas."""
    p = normalize_path(path)
    return any(p.startswith(pref) for pref in PROTECTED_PATH_PREFIXES)


def is_browse_path(path: str) -> bool:
    """Devuelve True para catálogo público, carrito y superficies de navegación del home."""
    p = normalize_path(path)
    if p in ('/', ''):
        return True
    return any(p == pref.rstrip('/') or p.startswith(pref) for pref in BROWSE_PATH_PREFIXES)


def seller_company_pending(user) -> bool:
    """Devuelve True cuando un vendedor aún no puede operar el portal.

    Falta ``Company.owner`` o falta ``CompanySubscription`` / plan activo.
    """
    if not user or not user.is_authenticated or user_is_platform_exempt(user):
        return False
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return False
    if profile.role != 'seller':
        return False
    if email_verification_required(user):
        return False
    from core.enterprise_models import CompanySubscription
    from core.models import Company

    company = Company.objects.filter(owner=user).first()
    if not company:
        return True
    try:
        company.subscription
    except CompanySubscription.DoesNotExist:
        return True
    return False


def seller_onboarding_redirect_name(user) -> str | None:
    """Devuelve el nombre de ruta del wizard de empresa cuando el onboarding de vendedor está incompleto."""
    if seller_company_pending(user):
        return 'seller_onboarding_company'
    return None


def buyer_onboarding_pending(user) -> bool:
    """Devuelve True cuando un comprador verificado aún necesita personalización."""
    if not user or not user.is_authenticated or user_is_platform_exempt(user):
        return False
    # OTP first — onboarding only after verified email (or if verification is off)
    if email_verification_required(user):
        return False
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return False
    if profile.role != 'buyer':
        return False
    return profile.onboarding_completed_at is None


def buyer_onboarding_redirect_name(user) -> str | None:
    """Devuelve la ruta del paso 1 de onboarding comprador cuando falta la personalización."""
    if buyer_onboarding_pending(user):
        return 'buyer_onboarding_step1'
    return None


def onboarding_redirect_name(user, scope: str = 'restricted') -> str | None:
    """Devuelve un nombre de ruta Django de redirección, o None si el usuario puede continuar."""
    if not user.is_authenticated or user_is_platform_exempt(user):
        return None

    if scope == 'browse':
        if user_needs_role_completion(user):
            return 'oauth_complete_signup'
        seller_route = seller_onboarding_redirect_name(user)
        if seller_route:
            return seller_route
        buyer_route = buyer_onboarding_redirect_name(user)
        if buyer_route:
            return buyer_route
        return None

    try:
        profile = user.profile
        if user.is_active and profile.email_verificado and profile.role:
            seller_route = seller_onboarding_redirect_name(user)
            if seller_route:
                return seller_route
            buyer_route = buyer_onboarding_redirect_name(user)
            if buyer_route:
                return buyer_route
            return None
    except UserProfile.DoesNotExist:
        if user_needs_role_completion(user):
            return 'oauth_complete_signup'
        return 'verificar_codigo'

    if user_needs_role_completion(user):
        return 'oauth_complete_signup'

    if not user.is_active:
        return 'pending_approval'

    if email_verification_required(user):
        return 'verificar_codigo'

    try:
        profile_role = user.profile.role
    except UserProfile.DoesNotExist:
        profile_role = None
    gate = application_gate_status(user.email or '', role=profile_role)
    if gate == 'required':
        return 'onboarding_solicitud_requerida'
    if gate in ('pending', 'under_review'):
        return 'pending_approval'
    if gate == 'rejected':
        return 'onboarding_aplicacion_rechazada'

    buyer_route = buyer_onboarding_redirect_name(user)
    if buyer_route:
        return buyer_route
    return None


def onboarding_context(user) -> dict:
    """Construye el contexto de plantilla para pantallas de espera de aprobación pendiente."""
    email = user.email or ''
    masked = _mask_email(email)
    app = latest_application_for_email(email)
    return {
        'masked_email': masked,
        'application': app,
        'application_status': app.get_status_display() if app else '',
    }


def _mask_email(email: str) -> str:
    """Enmascara la parte local de un correo para mostrarlo en pantallas de espera."""
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        visible = local[0] + '*'
    else:
        visible = local[0] + '*' * (len(local) - 2) + local[-1]
    return f'{visible}@{domain}'


def should_inline_verify_at_checkout(path: str, route: str | None) -> bool:
    """Devuelve True para incrustar OTP en el GET de checkout en lugar de /verificar."""
    if route != 'verificar_codigo':
        return False
    return normalize_path(path).startswith('/checkout')


def user_needs_otp_verification(user) -> bool:
    """Devuelve True cuando un usuario autenticado aún debe el OTP de correo."""
    if not email_verification_required(user):
        return False
    try:
        return not user.profile.email_verificado
    except UserProfile.DoesNotExist:
        return True


def safe_intent_next(request, *, raw: str = '') -> str:
    """Devuelve una URL interna segura de next tras el OTP (solo checkout/carrito)."""
    from django.urls import reverse

    next_url = (raw or request.GET.get('next') or request.POST.get('next') or '').strip()
    if not next_url:
        if request.method == 'GET':
            candidate = request.get_full_path()
        else:
            candidate = request.path
        p = normalize_path(candidate)
        if is_protected_path(p) or p.startswith('/carrito'):
            next_url = candidate
        else:
            return ''

    if not next_url.startswith('/') or next_url.startswith('//') or '://' in next_url:
        return ''

    verify_path = reverse('verificar_codigo')
    login_path = reverse('login')
    home_path = reverse('home')
    if (
        next_url.startswith(verify_path)
        or next_url.startswith(login_path)
        or next_url in (home_path, '/')
    ):
        return ''

    p = normalize_path(next_url.split('?', 1)[0])
    if is_protected_path(p) or p.startswith('/carrito'):
        return next_url
    return ''
