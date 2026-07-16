"""WSGI application entry for TradeFlow Colón.

Used by Gunicorn and similar sync servers; loads tradeflow_colon.settings
and exposes ``application`` as the WSGI callable.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradeflow_colon.settings')
application = get_wsgi_application()
