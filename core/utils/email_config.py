"""Comprueba si hay canal de envío real (Supabase o SMTP Django)."""
from django.conf import settings


def smtp_configured() -> bool:
    """True si Supabase está listo o EMAIL_BACKEND no es consola."""
    if getattr(settings, 'SUPABASE_CONFIGURED', False):
        return True
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    return 'console' not in backend and 'locmem' not in backend
