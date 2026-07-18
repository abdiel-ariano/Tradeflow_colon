"""Valida URLs de salida para bloquear SSRF (OWASP A10:2021).

Los webhooks logísticos configurados por el vendedor no deben alcanzar IPs
privadas ni endpoints de metadata cloud. ``safe_outbound_request`` conecta
al IP resuelto (DNS-pin) con SNI/Host del hostname original.
"""
from __future__ import annotations

import http.client
import ipaddress
import logging
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlparse

from django.core.exceptions import ValidationError

log = logging.getLogger('tradeflow.security')

ALLOWED_SCHEMES = ('http', 'https')

BLOCKED_HOSTNAMES = frozenset({
    'localhost', 'localhost.localdomain',
    'metadata.google.internal',
    'metadata',
    '169.254.169.254',
    '100.100.100.200',
})


def _is_blocked_ip(ip):
    """Devuelve True cuando la IP es privada, loopback o link-local."""
    if ip.is_loopback:
        return 'loopback (127.x / ::1)'
    if ip.is_private:
        return 'IP privada RFC 1918 (10.x, 172.16-31.x, 192.168.x)'
    if ip.is_link_local:
        return 'link-local (169.254.x / fe80::) — incluye metadata cloud'
    if ip.is_multicast:
        return 'multicast'
    if ip.is_reserved:
        return 'reservada'
    if ip.is_unspecified:
        return 'unspecified (0.0.0.0 / ::)'
    if isinstance(ip, ipaddress.IPv4Address) and str(ip) == '169.254.169.254':
        return 'AWS/Azure metadata service'
    return None


def _resolve_hostname(hostname):
    """Resuelve el hostname a direcciones IP para comprobaciones SSRF."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValidationError(f'No se pudo resolver el hostname "{hostname}": {exc}')
    for family, _, _, _, sockaddr in infos:
        addr_str = sockaddr[0]
        try:
            yield ipaddress.ip_address(addr_str)
        except ValueError:
            continue


@dataclass(frozen=True)
class SafeOutboundTarget:
    """Validated outbound URL with DNS-pinned public IP addresses."""

    url: str
    scheme: str
    hostname: str
    port: int
    path: str
    ips: tuple[str, ...]


def validate_outbound_url(url: str, *, allow_http: bool = False) -> SafeOutboundTarget:
    """Valida URL saliente y devuelve target con IPs públicas resueltas."""
    if not url or not isinstance(url, str):
        raise ValidationError('URL vacia o no es string.')

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        raise ValidationError(f'URL malformada: {exc}')

    scheme = (parsed.scheme or '').lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            f'Esquema "{scheme}" no permitido. Permitidos: {", ".join(ALLOWED_SCHEMES)}.'
        )
    if scheme == 'http' and not allow_http:
        raise ValidationError(
            'Se requiere https://. Solo se permite http:// si allow_http=True.'
        )

    hostname = (parsed.hostname or '').lower()
    if not hostname:
        raise ValidationError('La URL no tiene hostname.')

    if hostname in BLOCKED_HOSTNAMES:
        raise ValidationError(
            f'Hostname "{hostname}" esta en la blocklist (loopback/metadata service).'
        )
    if hostname == 'localhost' or hostname.endswith('.localhost'):
        raise ValidationError(f'Hostname "{hostname}" apunta a localhost.')

    safe_ips: list[str] = []
    try:
        literal_ip = ipaddress.ip_address(hostname.strip('[]'))
        reason = _is_blocked_ip(literal_ip)
        if reason:
            raise ValidationError(f'IP literal {literal_ip} bloqueada: {reason}.')
        safe_ips.append(str(literal_ip))
    except ValueError:
        for ip in _resolve_hostname(hostname):
            reason = _is_blocked_ip(ip)
            if reason:
                raise ValidationError(
                    f'El hostname "{hostname}" resuelve a {ip}, que esta bloqueada: {reason}.'
                )
            safe_ips.append(str(ip))

    if not safe_ips:
        raise ValidationError(f'No se obtuvo IP pública para "{hostname}".')

    blocked_ports = {22, 23, 25, 110, 143, 445, 631, 1433, 3306, 3389, 5432, 6379, 9200, 11211, 27017}
    port = parsed.port or (443 if scheme == 'https' else 80)
    if port in blocked_ports:
        raise ValidationError(
            f'Puerto {port} bloqueado (servicio interno tipico: SSH, SMTP, BD, Redis, etc.).'
        )

    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'

    return SafeOutboundTarget(
        url=url.strip(),
        scheme=scheme,
        hostname=hostname,
        port=port,
        path=path,
        ips=tuple(safe_ips),
    )


def safe_outbound_request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict | None = None,
    method: str = 'POST',
    timeout: float = 8,
    allow_http: bool = False,
) -> tuple[int, bytes]:
    """HTTP request pinned to a validated public IP (mitiga DNS rebinding)."""
    target = validate_outbound_url(url, allow_http=allow_http)
    hdrs = {k: v for k, v in (headers or {}).items()}
    hdrs.setdefault('Host', target.hostname)
    ip = target.ips[0]
    method = (method or 'GET').upper()

    if target.scheme == 'https':
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(ip, target.port, timeout=timeout, context=context)
        # Force SNI / cert validation against the original hostname.
        conn.host = target.hostname  # type: ignore[attr-defined]
    else:
        conn = http.client.HTTPConnection(ip, target.port, timeout=timeout)

    try:
        # Manually connect so TLS wraps with server_hostname=original host.
        if target.scheme == 'https':
            sock = socket.create_connection((ip, target.port), timeout=timeout)
            ssock = context.wrap_socket(sock, server_hostname=target.hostname)
            conn.sock = ssock
            conn.request(method, target.path, body=data, headers=hdrs)
        else:
            conn.request(method, target.path, body=data, headers=hdrs)
        resp = conn.getresponse()
        body = resp.read()
        status = resp.status
        log.info(
            'safe_outbound status=%s host=%s pinned_ip=%s',
            status, target.hostname, ip,
        )
        return status, body
    finally:
        try:
            conn.close()
        except Exception:
            pass
