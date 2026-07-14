from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    # Analítica embebida en el portal del vendedor (auto-carga su empresa).
    path("", views.seller_dashboard, name="seller_dashboard"),
    # Dashboard multi-fuente (standalone / admin); requiere login en integrado.
    path("admin/", views.dashboard, name="dashboard"),
    path("load/", views.load, name="load"),
    path("chat/", views.chat, name="chat"),
    path("clear/", views.clear, name="clear"),
    path("load-sheet/", views.load_sheet, name="load_sheet"),
    path("load-company/", views.load_company, name="load_company"),
    path("export/<str:fmt>/", views.export, name="export"),
    path("db/connect/", views.db_connect, name="db_connect"),
    path("db/disconnect/", views.db_disconnect, name="db_disconnect"),
    path("plotly.js", views.plotlyjs, name="plotlyjs"),
]
