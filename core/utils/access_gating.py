"""Gate buyers and sellers behind email OTP and access applications.

Public CFZ catalog browsing stays open; checkout, seller portal, and
enterprise APIs require verified email and (for buyers) approval when
``REQUIRE_APPROVED_APPLICATION`` is enabled.
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
    """Strip /en/ or /es/ locale prefix for gating comparisons."""
    p = path or '/'
    if p.startswith('/en/'):
        return p[3:] or '/'
    if p.startswith('/es/'):
        return p[3:] or '/'
    return p


def is_public_path(path: str) -> bool:
    """Return True when the path needs no auth or application gate."""
    p = normalize_path(path)
    if p in ('/', ''):
        return True
    return any(p == pref.rstrip('/') or p.startswith(pref) for pref in PUBLIC_PATH_PREFIXES)


def is_protected_path(path: str) -> bool:
    """Return True for checkout, orders, seller APIs, and other gated paths."""
    p = normalize_path(path)
    return any(p.startswith(pref) for pref in PROTECTED_PATH_PREFIXES)


def user_is_platform_exempt(user) -> bool:
    """Return True for anonymous, staff, superuser, or profile role admin."""
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
    """Return the newest ``UserApplication`` for ``email``, if any."""
    if not email:
        return None
    return (
        UserApplication.objects.filter(email__iexact=email.strip())
        .order_by('-created_at')
        .first()
    )


def application_gate_status(email: str, *, role: str | None = None) -> str | None:
    """Return application gate code, or None when access is allowed.
    
    
    Sellers skip manual approval (self-serve trial). Buyers may see
    ``pending``, ``rejected``, or ``required`` when gating is enabled.
    """
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
    """Return True when profile is missing or role is not buyer/seller/admin."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return True
    return profile.role not in ('buyer', 'seller', 'admin')


def email_verification_required(user) -> bool:
    """Return True when the user must finish email OTP before operational routes."""
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
    """Return True for checkout, orders, seller APIs, and other gated paths."""
    p = normalize_path(path)
    return any(p.startswith(pref) for pref in PROTECTED_PATH_PREFIXES)


def is_browse_path(path: str) -> bool:
    """Return True for public catalog, cart, and home browse surfaces."""
    p = normalize_path(path)
    if p in ('/', ''):
        return True
    return any(p == pref.rstrip('/') or p.startswith(pref) for pref in BROWSE_PATH_PREFIXES)


def seller_company_pending(user) -> bool:
    """Return True when a seller cannot operate the portal yet.
    
    
    Missing ``Company.owner`` or missing ``CompanySubscription`` both send
    the user back through the company wizard / trial start.
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
    """Return company-wizard route name when seller onboarding is incomplete."""
    if seller_company_pending(user):
        return 'seller_onboarding_company'
    return None


def buyer_onboarding_pending(user) -> bool:
    """Return True when a verified buyer still needs personalization wizard."""
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
    """Return buyer onboarding step-1 route when personalization is pending."""
    if buyer_onboarding_pending(user):
        return 'buyer_onboarding_step1'
    return None


def onboarding_redirect_name(user, scope: str = 'restricted') -> str | None:
    """Return a Django redirect route name, or None if the user may continue.
    
    
    ``browse`` only enforces OAuth role completion and seller/buyer wizards;
    ``restricted`` also enforces email verification and application gates.
    """
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
    """Build template context for pending-approval wait screens."""
    email = user.email or ''
    masked = _mask_email(email)
    app = latest_application_for_email(email)
    return {
        'masked_email': masked,
        'application': app,
        'application_status': app.get_status_display() if app else '',
    }


def _mask_email(email: str) -> str:
    """Mask local-part of an email for display on wait screens."""
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        visible = local[0] + '*'
    else:
        visible = local[0] + '*' * (len(local) - 2) + local[-1]
    return f'{visible}@{domain}'


def should_inline_verify_at_checkout(path: str, route: str | None) -> bool:
    """Return True to embed OTP on checkout GET instead of /verificar/."""
    if route != 'verificar_codigo':
        return False
    return normalize_path(path).startswith('/checkout')


def user_needs_otp_verification(user) -> bool:
    """Return True when an authenticated user still owes email OTP."""
    if not email_verification_required(user):
        return False
    try:
        return not user.profile.email_verificado
    except UserProfile.DoesNotExist:
        return True


def safe_intent_next(request, *, raw: str = '') -> str:
    """Return a safe internal next URL after OTP (checkout/cart only)."""
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
