"""
=============================================================================
TRADEFLOW COLÓN — core/apps.py
=============================================================================
Configuración de la aplicación 'core'.
Django usa esto para registrar la app en el proyecto.
=============================================================================
"""
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'TradeFlow Core'  # Nombre visible en el admin de Django
