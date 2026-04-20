"""
=============================================================================
TRADEFLOW COLÓN — urls.py (Raíz del proyecto)
=============================================================================
Este archivo es el "directorio telefónico" del proyecto.
Cada URL (dirección web) apunta a una vista (función que genera la página).

FLUJO: Usuario escribe URL → Django busca aquí → redirige a core/urls.py
=============================================================================
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Panel de administración de Django (usuarios, modelos, etc.)
    # Acceso: http://127.0.0.1:8000/admin/
    path('admin/', admin.site.urls),

    # Todas las URLs de nuestra app 'core' se definen en core/urls.py
    # El '' significa que están en la raíz (sin prefijo)
    path('', include('core.urls')),
]

# En desarrollo, Django sirve los archivos de media (imágenes subidas)
# En producción esto lo hace Nginx/Apache
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
