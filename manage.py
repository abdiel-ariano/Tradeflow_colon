#!/usr/bin/env python
"""
=============================================================================
TRADEFLOW COLÓN — manage.py
=============================================================================
Utilidad de línea de comandos de Django.

COMANDOS MÁS USADOS:
  python manage.py runserver          → Inicia el servidor en http://127.0.0.1:8000
  python manage.py migrate            → Aplica migraciones a la BD
  python manage.py makemigrations     → Genera archivos de migración
  python manage.py createsuperuser    → Crea usuario administrador
  python manage.py shell              → Consola Python con contexto Django
  python manage.py collectstatic      → Junta archivos estáticos (producción)
=============================================================================
"""
import os
import sys


def main():
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
