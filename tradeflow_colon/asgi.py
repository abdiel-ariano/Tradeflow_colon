"""Entrada ASGI de TradeFlow Colón.

La usan servidores con soporte async; carga tradeflow_colon.settings y
expone ``application`` como callable ASGI.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_asgi_application()
