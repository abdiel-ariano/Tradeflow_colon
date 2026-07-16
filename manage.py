#!/usr/bin/env python
"""Punto de entrada CLI de Django para TradeFlow Colón.

Define DJANGO_SETTINGS_MODULE y delega al runner de management para que
comandos locales y de CI compartan el mismo arranque.
"""
import os
import sys


def main():
    """Ejecuta un comando de management de Django desde sys.argv."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. ¿Activaste el entorno virtual?\n"
            "  Windows: .venv\\Scripts\\activate\n"
            "  Mac/Linux: source .venv/bin/activate"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
