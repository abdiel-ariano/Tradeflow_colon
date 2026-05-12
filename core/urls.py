"""
=============================================================================
TRADEFLOW COLÓN — core/urls.py  (v4 — Roles + Signup)
=============================================================================
"""
from django.urls import path
from . import views

urlpatterns = [

    # ── Autenticación ─────────────────────────────────────────────────────
    path('login/',   views.login_view,  name='login'),
    path('logout/',  views.logout_view, name='logout'),
    path('signup/',  views.signup_view, name='signup'),

    # ── Dashboard (admin) ─────────────────────────────────────────────────
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Portales de rol ───────────────────────────────────────────────────

    path('',           views.home_view,  name='home'),
    path('dashboard/', views.dashboard,  name='dashboard'),

    # Portal del comprador
    path('tienda/',                         views.tienda,               name='tienda'),
    path('carrito/',                         views.ver_carrito,         name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/quitar/<int:producto_id>/',  views.quitar_del_carrito, name='quitar_del_carrito'),
    path('checkout/',                        views.checkout,            name='checkout'),
    path('mis-ordenes/',                     views.mis_ordenes,         name='mis_ordenes'),
    path('mis-ordenes/<int:pk>/',            views.detalle_mi_orden,    name='detalle_mi_orden'),

    # Portal del vendedor
    path('mi-tienda/', views.portal_seller, name='portal_seller'),
    # Rutas solicitadas por especificación (nombres alternos)
    path('mi-tienda/productos/', views.seller_mis_productos, name='seller_mis_productos'),
    path('mi-tienda/productos/nuevo/', views.seller_agregar_producto, name='seller_agregar_producto'),
    path('mi-tienda/productos/<int:pk>/editar/', views.seller_editar_producto, name='seller_editar_producto'),
    path('mi-tienda/productos/<int:pk>/toggle/', views.seller_toggle_producto, name='seller_toggle_producto'),
    path('mi-tienda/ventas/', views.seller_mis_ventas, name='seller_mis_ventas'),
    path('mi-tienda/ventas/<int:pk>/', views.seller_detalle_venta, name='seller_detalle_venta'),
    # Compatibilidad con rutas previas
    path('mi-tienda/panel/', views.seller_dashboard, name='seller_dashboard'),
    path('mi-tienda/productos-legacy/', views.seller_productos, name='seller_productos'),
    path('mi-tienda/productos-legacy/nuevo/', views.seller_producto_nuevo, name='seller_producto_nuevo'),
    path('mi-tienda/productos-legacy/<int:pk>/editar/', views.seller_producto_editar, name='seller_producto_editar'),
    path('mi-tienda/ventas-legacy/', views.seller_ventas, name='seller_ventas'),
    path('mi-tienda/ventas-legacy/<int:pk>/', views.seller_venta_detalle, name='seller_venta_detalle'),

    # ── Órdenes (admin) ───────────────────────────────────────────────────
    path('ordenes/',                              views.lista_ordenes,        name='lista_ordenes'),
    path('ordenes/<int:pk>/',                     views.detalle_orden,        name='detalle_orden'),
    path('ordenes/<int:pk>/estado/<str:estado>/', views.cambiar_estado_orden, name='cambiar_estado_orden'),

    # ── Wizard Nueva Orden (admin) ────────────────────────────────────────
    path('ordenes/nueva/paso1/', views.nueva_orden_paso1, name='nueva_orden_paso1'),
    path('ordenes/nueva/paso2/', views.nueva_orden_paso2, name='nueva_orden_paso2'),
    path('ordenes/nueva/paso3/', views.nueva_orden_paso3, name='nueva_orden_paso3'),

    # ── Productos (admin) ─────────────────────────────────────────────────
    path('productos/', views.lista_productos, name='lista_productos'),

    # ── Empresas (admin) ──────────────────────────────────────────────────
    path('empresas/', views.lista_empresas, name='lista_empresas'),

    # ── API JSON ──────────────────────────────────────────────────────────
    path('api/productos/', views.api_productos, name='api_productos'),
]