"""
Locale helpers — Django forces LANGUAGE_CODE on unprefixed i18n URLs when
prefix_default_language=False, ignoring the language cookie. Redirect users
who chose a non-default language to the prefixed URL (e.g. /es/catalogo/).
"""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.http import HttpResponseRedirect
from django.utils import translation
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation.trans_real import check_for_language

from core.utils.i18n_urls import tf_translate_url


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

        path_lang = translation.get_language_from_path(request.path_info)
        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) or settings.LANGUAGE_CODE

        if path_lang:
            # Cookie wants default language but URL still has /es/ prefix (e.g. after EN switch).
            if (
                cookie_lang == settings.LANGUAGE_CODE
                and path_lang != settings.LANGUAGE_CODE
                and cookie_lang in dict(settings.LANGUAGES)
                and check_for_language(cookie_lang)
            ):
                translated = tf_translate_url(request.get_full_path(), cookie_lang)
                if translated != request.get_full_path():
                    response = self.response_redirect_class(translated)
                    patch_vary_headers(response, ('Accept-Language', 'Cookie'))
                    return response
            return None

        if cookie_lang == settings.LANGUAGE_CODE:
            return None
        if cookie_lang not in dict(settings.LANGUAGES) or not check_for_language(cookie_lang):
            return None

        translated = tf_translate_url(request.get_full_path(), cookie_lang)
        if translated == request.get_full_path():
            return None

        response = self.response_redirect_class(translated)
        patch_vary_headers(response, ('Accept-Language', 'Cookie'))
        return response
