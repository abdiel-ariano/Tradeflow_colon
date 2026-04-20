"""
WSGI config para TradeFlow Colón.
Expone la aplicación WSGI como variable de módulo llamada `application`.
Documentación: https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_wsgi_application()
