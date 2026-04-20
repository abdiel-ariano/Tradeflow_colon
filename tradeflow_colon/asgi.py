"""
ASGI config para TradeFlow Colón.
Expone la aplicación ASGI como variable de módulo llamada `application`.
Documentación: https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_asgi_application()
