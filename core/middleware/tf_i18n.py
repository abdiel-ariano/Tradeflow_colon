"""
Locale helpers — Django forces LANGUAGE_CODE on unprefixed i18n URLs when
prefix_default_language=False, ignoring the language cookie. Redirect users
who chose a non-default language to the prefixed URL (e.g. /es/catalogo/).
"""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.http import HttpResponseRedirect
from django.urls import translate_url
from django.utils import translation
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation.trans_real import check_for_language


class TfLanguagePrefixRedirectMiddleware(MiddlewareMixin):
    """Redirect unprefixed paths to the cookie language prefix when needed."""

    response_redirect_class = HttpResponseRedirect

    def process_request(self, request):
        if request.method not in ('GET', 'HEAD'):
            return None

        urlconf = getattr(request, 'urlconf', settings.ROOT_URLCONF)
        i18n_patterns_used, prefixed_default_language = is_language_prefix_patterns_used(urlconf)
        if not i18n_patterns_used or prefixed_default_language:
            return None

        if translation.get_language_from_path(request.path_info):
            return None

        lang_code = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if not lang_code or lang_code == settings.LANGUAGE_CODE:
            return None
        if lang_code not in dict(settings.LANGUAGES) or not check_for_language(lang_code):
            return None

        translated = translate_url(request.get_full_path(), lang_code)
        if translated == request.get_full_path():
            return None

        response = self.response_redirect_class(translated)
        patch_vary_headers(response, ('Accept-Language', 'Cookie'))
        return response
