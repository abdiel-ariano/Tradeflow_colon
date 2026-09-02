"""Serve a maintenance page when the database cannot be reached.

PaaS cold starts and Postgres outages should return 503 with Retry-After
instead of opaque Django 500 pages for CFZ marketplace visitors.
"""
from __future__ import annotations

from django.db import DatabaseError, OperationalError
from django.http import HttpResponse
from django.template import loader
from django.utils.deprecation import MiddlewareMixin


class DatabaseUnavailableMiddleware(MiddlewareMixin):
    """Catch connection-class DB errors and render a 503 maintenance page."""

    def process_exception(self, request, exception):
        """Return 503 for auth/connect/timeout DB failures; else continue."""
        if not isinstance(exception, (OperationalError, DatabaseError)):
            return None
        message = str(exception).lower()
        if (
            'authentication failed' not in message
            and 'could not connect' not in message
            and 'timeout' not in message
            and 'connection' not in message
        ):
            return None

        template = loader.get_template('core/errors/db_unavailable.html')
        body = template.render({}, request)
        response = HttpResponse(body, status=503)
        response['Retry-After'] = '120'
        return response
