"""URL routes for seller and staff Analytics IA dashboards.

Seller portal mounts the embedded dashboard at the app root; staff
admin paths cover multi-source load, DB connect, chat, and export.
"""
from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    # Embedded seller portal analytics (auto-loads owner company).
    path("", views.seller_dashboard, name="seller_dashboard"),
    # Multi-source dashboard (standalone / staff); login when integrated.
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
