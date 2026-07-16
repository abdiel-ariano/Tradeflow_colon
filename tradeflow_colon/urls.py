"""Root URLConf for TradeFlow Colón.

Mounts admin, i18n language switching, and health probes outside i18n
patterns; marketplace routes live under optional /en/ prefixes with
Spanish as the unprefixed default.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from core import views_platform
from core import views_i18n

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', views_i18n.set_language, name='set_language'),
    path('health/live/', views_platform.health_live, name='health_live'),
    path('health/ready/', views_platform.health_ready, name='health_ready'),
]

urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, 'SERVE_LOCAL_MEDIA', False):
    # Docker demo / local files when DEBUG=False (do not enable in production S3-only deploys).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
