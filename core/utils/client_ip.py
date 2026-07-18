"""Trusted client IP extraction for rate limits, axes, and audit logs.

Prefer the rightmost ``X-Forwarded-For`` hop so forged prefixes cannot
override the address appended by the edge proxy (Railway / nginx).
"""
from __future__ import annotations


def get_client_ip(request) -> str:
    """Return the best-effort client IP for security controls (max 45 chars)."""
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if xff:
        parts = [p.strip() for p in xff.split(',') if p.strip()]
        if parts:
            return parts[-1][:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]
