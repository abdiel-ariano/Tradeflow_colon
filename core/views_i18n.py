"""Locale switcher for ``prefix_default_language=False`` URL layouts.

Django's stock ``set_language`` cannot rewrite ``/es/...`` paths when
the default language has no prefix. Marketplace pages (guest catalog,
seller portal, OTP) keep the same route under the chosen locale.
"""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language
from django.views.decorators.http import require_http_methods

from core.utils.i18n_urls import tf_translate_url


@require_http_methods(['GET', 'POST'])
def set_language(request):
    """Set the language cookie and redirect to the matching locale URL.

    Accepts ``language`` and ``next`` from POST or GET. Rejects open
    redirects, then uses ``tf_translate_url`` so CFZ marketplace paths
    stay correct without a default-language prefix.
    """
    next_url = request.POST.get('next', request.GET.get('next'))
    if (
        next_url or request.accepts('text/html')
    ) and not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = request.META.get('HTTP_REFERER')
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = '/'
    if not next_url:
        next_url = '/'

    lang_code = request.POST.get('language', request.GET.get('language'))
    target_url = next_url
    if request.method == 'POST' and lang_code and check_for_language(lang_code):
        target_url = tf_translate_url(next_url, lang_code)

    response = HttpResponseRedirect(target_url)
    if request.method == 'POST' and lang_code and check_for_language(lang_code):
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
    return response
