"""ASGI application entry for TradeFlow Colón.

Used by async-capable servers; loads tradeflow_colon.settings and exposes
``application`` as the ASGI callable.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_asgi_application()
