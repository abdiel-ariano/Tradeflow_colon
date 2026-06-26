"""
=============================================================================
TRADEFLOW COLÓN — urls.py (Raíz del proyecto)
=============================================================================
Incluye prefijos de idioma opcionales (es por defecto sin prefijo; en → /en/...).
=============================================================================
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from core import views_platform

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('health/live/', views_platform.health_live, name='health_live'),
    path('health/ready/', views_platform.health_ready, name='health_ready'),
]

urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    prefix_default_language=False,
)

def _serve_local_media_files():
    if settings.DEBUG or getattr(settings, 'SERVE_LOCAL_MEDIA', False):
        return True
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    return 'FileSystemStorage' in backend


if _serve_local_media_files():
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
