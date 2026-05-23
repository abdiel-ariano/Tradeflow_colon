"""
=============================================================================
TRADEFLOW COLÓN — core/urls.py  (v4 — Roles + Signup)
=============================================================================
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from . import views_onboarding as onboarding
from . import views_transportistas as vt
from . import views_api_enterprise as vapi

urlpatterns = [

    # ── Mapa ZLC + QR visitante ─────────────────────────────────────────────
    path('mapa/', views.mapa_zlc, name='mapa_zlc'),
    path('visitante/zlc/', views.visitante_zlc_verificacion, name='visitante_zlc_verificacion'),
    path('mi-qr/', views.mi_qr, name='mi_qr'),
    path('mi-qr/descargar/', views.generar_qr_visitante, name='descargar_qr'),

    # ── Autenticación ─────────────────────────────────────────────────────
    path('login/',   views.login_view,  name='login'),
    path(
        'recuperar-clave/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            html_email_template_name='registration/password_reset_email_html.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url='/recuperar-clave/enviado/',
        ),
        name='password_reset',
    ),
    path(
        'recuperar-clave/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'recuperar-clave/confirmar/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/recuperar-clave/completo/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'recuperar-clave/completo/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('logout/',  views.logout_view, name='logout'),
    path('signup/',  views.signup_view, name='signup'),
    path('solicitud-acceso/', views.solicitud_acceso, name='solicitud_acceso'),
    path('onboarding/solicitud-enviada/', onboarding.onboarding_solicitud_enviada, name='onboarding_solicitud_enviada'),
    path('onboarding/verificar-email/', onboarding.onboarding_espera_verificacion, name='onboarding_espera_verificacion'),
    path('onboarding/espera-aprobacion/', onboarding.onboarding_espera_aprobacion, name='onboarding_espera_aprobacion'),
    path('onboarding/acceso-requerido/', onboarding.onboarding_solicitud_requerida, name='onboarding_solicitud_requerida'),
    path('onboarding/solicitud-rechazada/', onboarding.onboarding_aplicacion_rechazada, name='onboarding_aplicacion_rechazada'),
    path('onboarding/reenviar-verificacion/', onboarding.onboarding_reenviar_verificacion, name='onboarding_reenviar_verificacion'),
    path('api/onboarding/verification-status/', onboarding.api_onboarding_verification_status, name='api_onboarding_verification_status'),
    path(
        'solicitud-acceso/revisar/<str:token>/<str:accion>/',
        views.revisar_solicitud,
        name='revisar_solicitud',
    ),
    path('transportistas/aplicar/', vt.aplicar_transportista, name='aplicar_transportista'),
    path(
        'transportistas/seleccionar/<int:order_pk>/',
        vt.seleccionar_transportista,
        name='seleccionar_transportista',
    ),
    path('admin/transportistas/', vt.admin_transportistas, name='admin_transportistas'),
    path(
        'admin/transportistas/<int:pk>/<str:decision>/',
        vt.admin_aprobar_transportista,
        name='admin_aprobar_transportista',
    ),
    path(
        'ordenes/<int:order_pk>/confirmar/<str:decision>/',
        vt.confirmar_orden_empresa,
        name='confirmar_orden_empresa',
    ),
    path('verificar-email/<str:token>/', views.verificar_email, name='verificar_email'),
    path('reenviar-verificacion/', views.reenviar_verificacion, name='reenviar_verificacion'),
    path('reenviar-verificacion-email/', views.reenviar_verificacion_public, name='reenviar_verificacion_public'),
    path('perfil/',  views.mi_perfil, name='mi_perfil'),

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
    path('ordenes/<int:orden_pk>/factura/',  views.descargar_factura,   name='descargar_factura'),
    path('ordenes/<int:orden_pk>/packing-list/', views.descargar_packing_list, name='descargar_packing_list'),

    path('cotizaciones/', views.mis_cotizaciones, name='mis_cotizaciones'),
    path('cotizaciones/nueva/', views.solicitar_cotizacion, name='solicitar_cotizacion'),
    path('cotizaciones/<int:pk>/', views.detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizaciones/<int:pk>/pdf/', views.descargar_cotizacion_pdf, name='descargar_cotizacion_pdf'),

    # Portal del vendedor
    path('mi-tienda/', views.portal_seller, name='portal_seller'),
    path('api/seller-dashboard/', views.api_seller_dashboard, name='api_seller_dashboard'),
    path(
        'api/seller/orders/<int:pk>/timeline/',
        views.api_seller_order_timeline,
        name='api_seller_order_timeline',
    ),
    path('mi-tienda/plan/', views.seller_plan_consumo, name='seller_plan_consumo'),
    path('mi-tienda/plan/upgrade/', views.seller_upgrade_plan, name='seller_upgrade_plan'),
    path('mi-tienda/ventas/<int:pk>/despachar/', views.seller_dispatch_order, name='seller_dispatch_order'),

    path('api/v1/health/', vapi.api_v1_health, name='api_v1_health'),
    path('api/v1/inventory/', vapi.api_v1_inventory, name='api_v1_inventory'),
    path('api/v1/pricing/sync/', vapi.api_v1_pricing_sync, name='api_v1_pricing_sync'),
    # Rutas solicitadas por especificación (nombres alternos)
    path('mi-tienda/productos/', views.seller_mis_productos, name='seller_mis_productos'),
    path('mi-tienda/productos/nuevo/', views.seller_agregar_producto, name='seller_agregar_producto'),
    path('mi-tienda/productos/<int:pk>/editar/', views.seller_editar_producto, name='seller_editar_producto'),
    path('mi-tienda/productos/<int:pk>/toggle/', views.seller_toggle_producto, name='seller_toggle_producto'),
    path('mi-tienda/ventas/', views.seller_mis_ventas, name='seller_mis_ventas'),
    path('mi-tienda/ventas/exportar.csv', views.seller_export_ventas_csv, name='seller_export_ventas_csv'),
    path('mi-tienda/ventas/<int:pk>/', views.seller_detalle_venta, name='seller_detalle_venta'),
    path('mi-tienda/cotizaciones/', views.seller_cotizaciones, name='seller_cotizaciones'),
    path('mi-tienda/cotizaciones/<int:pk>/responder/', views.seller_responder_cotizacion, name='seller_responder_cotizacion'),
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

    # ── Dashboard API (Chart.js, sin recarga) ─────────────────────────────
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),

    # ── API JSON ──────────────────────────────────────────────────────────
    path('api/productos/', views.api_productos, name='api_productos'),
    path('api/home-merchandising/', views.api_home_merchandising, name='api_home_merchandising'),
    path('api/asistente/', views.api_asistente, name='api_asistente'),
]
