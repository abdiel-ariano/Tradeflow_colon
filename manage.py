#!/usr/bin/env python
"""Django CLI entrypoint for TradeFlow Colón.

Sets DJANGO_SETTINGS_MODULE and delegates to Django's management runner
so local and CI commands share one bootstrap path.
"""
import os
import sys


def main():
    """Run a Django management command from sys.argv."""
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
