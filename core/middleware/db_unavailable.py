"""Return 503 when the database is unreachable instead of opaque 500 pages."""
from __future__ import annotations

from django.db import DatabaseError, OperationalError
from django.http import HttpResponse
from django.template import loader
from django.utils.deprecation import MiddlewareMixin


class DatabaseUnavailableMiddleware(MiddlewareMixin):
    """Catch DB connection errors and show a maintenance response."""

    def process_exception(self, request, exception):
        """Process exception."""
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
