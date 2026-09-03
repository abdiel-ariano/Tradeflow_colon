"""URLConf raíz de TradeFlow Colón.

Monta admin, cambio de idioma e health checks fuera de i18n; las rutas
del marketplace van bajo prefijos /en/ opcionales, con español por
defecto sin prefijo.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from core import views_platform
from core import views_i18n
from core.views.stripe_checkout import stripe_webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', views_i18n.set_language, name='set_language'),
    path('health/live/', views_platform.health_live, name='health_live'),
    path('health/ready/', views_platform.health_ready, name='health_ready'),
    path('webhooks/stripe/', stripe_webhook, name='stripe_webhook'),
    # Root-scoped platform resources are not translated.
    path(
        '.well-known/assetlinks.json',
        views_platform.assetlinks_json,
        name='assetlinks_json',
    ),
    path(
        '.well-known/security.txt',
        views_platform.security_txt,
        name='security_txt',
    ),
    path(
        'manifest.webmanifest',
        views_platform.web_app_manifest,
        name='web_app_manifest',
    ),
    path(
        'service-worker.js',
        views_platform.service_worker,
        name='service_worker',
    ),
    path(
        'pwa/icon-<int:size>.png',
        views_platform.pwa_icon,
        name='pwa_icon',
    ),
    path('offline/', views_platform.offline_page, name='offline_page'),
    path(
        'security.txt',
        views_platform.security_txt,
        name='security_txt_legacy',
    ),
    path('robots.txt', views_platform.robots_txt, name='robots_txt'),
]

urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, 'SERVE_LOCAL_MEDIA', False):
    # Demo Docker / archivos locales con DEBUG=False (no usar en prod solo-S3).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
