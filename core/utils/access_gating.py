"""
Control de acceso enterprise: verificación de email y solicitud aprobada.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import UserApplication, UserProfile

# Rutas siempre públicas (sin prefijo /en/)
PUBLIC_PATH_PREFIXES = (
    '/login',
    '/signup',
    '/logout',
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
    '/tienda',
    '/carrito',
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
    '/api/home-merchandising',
    '/api/dashboard-stats',
)


def normalize_path(path: str) -> str:
    p = path or '/'
    if p.startswith('/en/'):
        return p[3:] or '/'
    if p.startswith('/es/'):
        return p[3:] or '/'
    return p


def is_public_path(path: str) -> bool:
    p = normalize_path(path)
    if p in ('/', ''):
        return True
    return any(p == pref.rstrip('/') or p.startswith(pref) for pref in PUBLIC_PATH_PREFIXES)


def is_protected_path(path: str) -> bool:
    p = normalize_path(path)
    return any(p.startswith(pref) for pref in PROTECTED_PATH_PREFIXES)


def user_is_platform_exempt(user) -> bool:
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
    if not email:
        return None
    return (
        UserApplication.objects.filter(email__iexact=email.strip())
        .order_by('-created_at')
        .first()
    )


def application_gate_status(email: str) -> str | None:
    """
    None = acceso OK respecto a solicitud.
    Otros: pending, under_review, rejected, required.
    """
    if not getattr(settings, 'REQUIRE_APPROVED_APPLICATION', False):
        return None

    app = latest_application_for_email(email)
    if not app:
        if getattr(settings, 'ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION', False):
            return None
        return 'required'

    if app.status == 'aprobada':
        return None
    if app.status == 'rechazada':
        return 'rejected'
    if app.status == 'en_revision':
        return 'under_review'
    if app.status == 'pendiente':
        return 'pending'
    return 'pending'


def email_verification_required(user) -> bool:
    if not getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False):
        return False
    if user_is_platform_exempt(user):
        return False
    try:
        return not user.profile.email_verificado
    except UserProfile.DoesNotExist:
        return True


def onboarding_redirect_name(user) -> str | None:
    """
    Nombre de ruta Django para redirigir, o None si el usuario puede continuar.
    """
    if not user.is_authenticated or user_is_platform_exempt(user):
        return None

    if not user.is_active:
        return 'pending_approval'

    if email_verification_required(user):
        return 'verificar_codigo'

    gate = application_gate_status(user.email or '')
    if gate == 'required':
        return 'onboarding_solicitud_requerida'
    if gate in ('pending', 'under_review'):
        return 'pending_approval'
    if gate == 'rejected':
        return 'onboarding_aplicacion_rechazada'
    return None


def onboarding_context(user) -> dict:
    """Contexto para pantallas de espera."""
    email = user.email or ''
    masked = _mask_email(email)
    app = latest_application_for_email(email)
    return {
        'masked_email': masked,
        'application': app,
        'application_status': app.get_status_display() if app else '',
    }


def _mask_email(email: str) -> str:
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        visible = local[0] + '*'
    else:
        visible = local[0] + '*' * (len(local) - 2) + local[-1]
    return f'{visible}@{domain}'
