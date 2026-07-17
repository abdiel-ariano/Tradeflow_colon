"""Traduce rutas cuando el locale por defecto no tiene prefijo de URL.

Django ``translate_url`` falla con ``prefix_default_language=False``;
estos helpers quitan y reponen ``/es`` o ``/en`` de forma segura.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils.translation import get_language_from_path, override


def _strip_language_prefix(path: str) -> tuple[str | None, str]:
    """Devuelve (language_code, path_without_prefix)."""
    lang = get_language_from_path(path)
    if not lang:
        return None, path
    prefix = f'/{lang}'
    if path == prefix:
        return lang, '/'
    if path.startswith(f'{prefix}/'):
        return lang, path[len(prefix):] or '/'
    return lang, path


def _add_language_prefix(path: str, lang_code: str) -> str:
    """Antepone el locale a la ruta salvo que sea el LANGUAGE_CODE por defecto."""
    if lang_code == settings.LANGUAGE_CODE:
        return path
    if path == '/':
        return f'/{lang_code}/'
    return f'/{lang_code}{path}'


def tf_translate_url(url: str, lang_code: str) -> str:
    """Traduce una ruta a otro locale sin prefijo del idioma por defecto.


    Quita el prefijo activo antes de resolve/reverse y cae a añadir/quitar
    prefijo manualmente cuando resolve no está disponible en middleware temprano.
    """
    parsed = urlsplit(url)
    path = parsed.path or '/'
    current_lang, neutral_path = _strip_language_prefix(path)

    try:
        match = resolve(neutral_path)
    except Resolver404:
        new_path = (
            _add_language_prefix(neutral_path, lang_code)
            if lang_code != settings.LANGUAGE_CODE
            else neutral_path
        )
        return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))

    to_be_reversed = (
        f'{match.namespace}:{match.url_name}' if match.namespace else match.url_name
    )
    with override(lang_code):
        try:
            new_path = reverse(to_be_reversed, args=match.args, kwargs=match.kwargs)
        except NoReverseMatch:
            new_path = (
                _add_language_prefix(neutral_path, lang_code)
                if lang_code != settings.LANGUAGE_CODE
                else neutral_path
            )

    return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))
