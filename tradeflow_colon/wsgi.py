"""Entrada WSGI de TradeFlow Colón.

La usan Gunicorn y servidores síncronos similares; carga
tradeflow_colon.settings y expone ``application`` como callable WSGI.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_wsgi_application()
