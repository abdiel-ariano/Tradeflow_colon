"""Utilidades para sembrar usuarios demo sin contraseñas en el repositorio."""
from __future__ import annotations

import os

from django.utils.crypto import get_random_string


def demo_user_password(*, allow_generate: bool = True) -> str:
    """Devuelve la clave demo desde DEMO_USER_PASSWORD o una aleatoria local.

    La clave nunca se almacena en código fuente. En entornos de evaluación,
  defina DEMO_USER_PASSWORD en el entorno antes de ejecutar ``cargar_demo``.
    """
    configured = (os.environ.get('DEMO_USER_PASSWORD') or '').strip()
    if configured:
        return configured
    if allow_generate:
        return get_random_string(
            20,
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        )
    return ''
