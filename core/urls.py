"""
=============================================================================
TRADEFLOW COLÓN — core/urls.py
=============================================================================
App URL table mounted under ``i18n_patterns`` (see tradeflow_colon/urls.py).

Groups (in file order):
  - Legal / marketing pages
  - Auth, signup, OAuth, password reset
  - Email OTP verification
  - Admin dashboard, orders wizard, products, companies
  - Seller portal (/mi-tienda/…)
  - Buyer catalog, cart, checkout, RFQ
  - JSON APIs (/api/…)
  - Enterprise API (/api/v1/…) via views_api_enterprise
  - Transport carriers, onboarding wizards

Name every ``path()`` — templates and emails depend on reverse().
=============================================================================
"""
from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import views
from . import views_seller_pages
from . import views_social
from . import views_onboarding as onboarding
from . import views_buyer_onboarding as buyer_onboarding
from . import views_transportistas as vt
from . import views_api_enterprise as vapi

urlpatterns = [

    # ── Mapa ZLC + verificación visitante ───────────────────────────────────
    path('mapa/', views.mapa_zlc, name='mapa_zlc'),
    path('visitante/zlc/', views.visitante_zlc_verificacion, name='visitante_zlc_verificacion'),

    # ── Páginas legales ─────────────────────────────────────────────────────
    path('terminos/', views.legal_terminos, name='legal_terminos'),
    path('privacidad/', views.legal_privacidad, name='legal_privacidad'),
    path('cookies/', views.legal_cookies, name='legal_cookies'),
    path('acerca/', views.acerca_tradeflow, name='acerca_tradeflow'),
    path('verified-suppliers/', views.marketplace_verified_suppliers, name='marketplace_verified_suppliers'),
    path('deals/', views.marketplace_deals, name='marketplace_deals'),
    path('order-protection/', views.marketplace_order_protection, name='marketplace_order_protection'),

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
    path('signup/comprador/', views.signup_buyer_view, name='signup_buyer'),
    path('signup/vendedor/', views.signup_seller_view, name='signup_seller'),
    path(
        'signup/oauth/begin/<str:provider>/',
        views_social.oauth_begin_signup,
        name='oauth_begin_signup',
    ),
    path(
        'login/oauth/begin/<str:provider>/',
        views_social.oauth_begin_login,
        name='oauth_begin_login',
    ),
    path(
        'signup/oauth/completar/',
        views_social.oauth_complete_signup,
        name='oauth_complete_signup',
    ),
    path(
        'signup/oauth/finalizar/',
        views_social.oauth_post_signup,
        name='oauth_post_signup',
    ),
    path('accounts/login/', views_social.redirect_accounts_login),
    path('accounts/signup/', views_social.redirect_accounts_signup),
    path('accounts/inactive/', views_social.redirect_accounts_inactive),
    path('accounts/', include('allauth.urls')),
    path('solicitud-acceso/', views.solicitud_acceso, name='solicitud_acceso'),
    path('onboarding/solicitud-enviada/', onboarding.onboarding_solicitud_enviada, name='onboarding_solicitud_enviada'),
    path('onboarding/verificar-email/', onboarding.onboarding_espera_verificacion, name='onboarding_espera_verificacion'),
    path('onboarding/espera-aprobacion/', onboarding.onboarding_espera_aprobacion, name='onboarding_espera_aprobacion'),
    path('onboarding/acceso-requerido/', onboarding.onboarding_solicitud_requerida, name='onboarding_solicitud_requerida'),
    path('onboarding/solicitud-rechazada/', onboarding.onboarding_aplicacion_rechazada, name='onboarding_aplicacion_rechazada'),
    path('onboarding/reenviar-verificacion/', onboarding.onboarding_reenviar_verificacion, name='onboarding_reenviar_verificacion'),
    path('onboarding/verificar-codigo/', onboarding.onboarding_verificar_codigo, name='onboarding_verificar_codigo'),
    path('api/onboarding/verification-status/', onboarding.api_onboarding_verification_status, name='api_onboarding_verification_status'),
    # Wizard comprador — personalización post-registro (3 pasos)
    path('onboarding/comprador/', buyer_onboarding.buyer_onboarding_step1, name='buyer_onboarding_step1'),
    path('onboarding/comprador/paso-1/', buyer_onboarding.buyer_onboarding_step1_post, name='buyer_onboarding_step1_post'),
    path('onboarding/comprador/categorias/', buyer_onboarding.buyer_onboarding_step2, name='buyer_onboarding_step2'),
    path('onboarding/comprador/categorias/guardar/', buyer_onboarding.buyer_onboarding_step2_post, name='buyer_onboarding_step2_post'),
    path('onboarding/comprador/busqueda/', buyer_onboarding.buyer_onboarding_step3, name='buyer_onboarding_step3'),
    path('onboarding/comprador/finalizar/', buyer_onboarding.buyer_onboarding_finish, name='buyer_onboarding_finish'),
    path('onboarding/comprador/omitir/', buyer_onboarding.buyer_onboarding_skip, name='buyer_onboarding_skip'),
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
    path('verificar/enviar/', views.enviar_codigo, name='enviar_codigo'),
    path('verificar/', views.verificar_codigo, name='verificar_codigo'),
    path('verificar/otp/', views.verificar_codigo, name='verify_otp'),
    path('verificar-email/<str:token>/', views.verificar_email, name='verificar_email'),
    path('reenviar-verificacion/', views.reenviar_verificacion, name='reenviar_verificacion'),
    path('reenviar-verificacion-email/', views.reenviar_verificacion_public, name='reenviar_verificacion_public'),
    path('perfil/',  views.mi_perfil, name='mi_perfil'),

    # ── Dashboard (admin) ─────────────────────────────────────────────────
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('saas/', views.admin_saas_dashboard, name='admin_saas_dashboard'),

    # ── Portales de rol ───────────────────────────────────────────────────

    path('',           views.home_view,  name='home'),
    path('dashboard/', views.dashboard,  name='dashboard'),

    # Portal del comprador
    path('catalogo/',                       views.catalogo_publico,     name='catalogo_publico'),
    path('catalogo/inquiry/agregar/<int:producto_id>/', views.catalogo_agregar_inquiry, name='catalogo_agregar_inquiry'),
    path('catalogo/producto/<int:pk>/', views.catalogo_producto_detail, name='catalogo_producto_detail'),
    path('tienda/',                         views.tienda,               name='tienda'),
    path('carrito/',                         views.ver_carrito,         name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/quitar/<int:producto_id>/',  views.quitar_del_carrito, name='quitar_del_carrito'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('carrito/vaciar/',                  views.vaciar_carrito,      name='vaciar_carrito'),
    path('checkout/',                        views.checkout,            name='checkout'),
    path('mis-ordenes/',                     views.mis_ordenes,         name='mis_ordenes'),
    path('mis-ordenes/<int:pk>/',            views.detalle_mi_orden,    name='detalle_mi_orden'),
    path('ordenes/<int:orden_pk>/factura/',  views.descargar_factura,   name='descargar_factura'),
    path('ordenes/<int:orden_pk>/packing-list/', views.descargar_packing_list, name='descargar_packing_list'),

    path('cotizaciones/', views.mis_cotizaciones, name='mis_cotizaciones'),
    path('cotizaciones/nueva/', views.solicitar_cotizacion, name='solicitar_cotizacion'),
    path('cotizaciones/automatica/<int:producto_id>/', views.solicitar_cotizacion_automatica, name='solicitar_cotizacion_automatica'),
    path('cotizaciones/comparar/<str:lote>/', views.comparar_cotizaciones, name='comparar_cotizaciones'),
    path('cotizaciones/<int:pk>/', views.detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizaciones/<int:pk>/pdf/', views.descargar_cotizacion_pdf, name='descargar_cotizacion_pdf'),

    # Portal del vendedor
    path('mi-tienda/', views.portal_seller, name='portal_seller'),
    path('mi-tienda/qr/', views.seller_company_qr, name='seller_company_qr'),
    path('mi-tienda/qr/descargar/', views.seller_download_qr, name='seller_download_qr'),
    path('api/seller-dashboard/', views.api_seller_dashboard, name='api_seller_dashboard'),
    path(
        'api/seller/orders/<int:pk>/timeline/',
        views.api_seller_order_timeline,
        name='api_seller_order_timeline',
    ),
    path('mi-tienda/plan/', views.seller_plan_consumo, name='seller_plan_consumo'),
    path('mi-tienda/plan/pago/<slug:plan_slug>/', views.seller_plan_checkout, name='seller_plan_checkout'),
    path(
        'mi-tienda/plan/pago/<slug:plan_slug>/confirmar/',
        views.seller_plan_checkout_pay,
        name='seller_plan_checkout_pay',
    ),
    path('mi-tienda/plan/pago/pendiente/', views.seller_plan_checkout_resume, name='seller_plan_checkout_resume'),
    path('mi-tienda/plan/upgrade/', views.seller_upgrade_plan, name='seller_upgrade_plan'),
    path('mi-tienda/insights/', views.seller_predictive_insights, name='seller_predictive_insights'),
    path('mi-tienda/balances/', views_seller_pages.seller_balances, name='seller_balances'),
    path('mi-tienda/clientes/', views_seller_pages.seller_customers, name='seller_customers'),
    path('mi-tienda/impuestos/', views_seller_pages.seller_tax, name='seller_tax'),
    path('mi-tienda/datos/', views_seller_pages.seller_data_management, name='seller_data_management'),
    path('mi-tienda/disputas/', views_seller_pages.seller_disputes, name='seller_disputes'),
    path('mi-tienda/apps/', views_seller_pages.seller_apps, name='seller_apps'),
    path('mi-tienda/configuracion/', views_seller_pages.seller_setup_guide, name='seller_setup_guide'),
    path('mi-tienda/buscar/', views_seller_pages.seller_global_search, name='seller_global_search'),
    path('mi-tienda/reportes/', views_seller_pages.seller_reporting, name='seller_reporting'),
    # Analítica IA (app 'analytics'): dashboard del vendedor + chat/export/plotly.js.
    path('mi-tienda/analitica/', include('analytics.urls')),
    path('mi-tienda/ventas/<int:pk>/despachar/', views.seller_dispatch_order, name='seller_dispatch_order'),

    path('api/v1/health/', vapi.api_v1_health, name='api_v1_health'),
    path('api/v1/inventory/', vapi.api_v1_inventory, name='api_v1_inventory'),
    path('api/v1/pricing/sync/', vapi.api_v1_pricing_sync, name='api_v1_pricing_sync'),
    # Rutas solicitadas por especificación (nombres alternos)
    path('mi-tienda/productos/', views.seller_mis_productos, name='seller_mis_productos'),
    path('mi-tienda/productos/exportar.csv', views.seller_export_productos_csv, name='seller_export_productos_csv'),
    path('mi-tienda/productos/exportar-precios.csv', views.seller_export_precios_csv, name='seller_export_precios_csv'),
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
    path('api/admin/saas-stats/', views.api_admin_saas_stats, name='api_admin_saas_stats'),
    path(
        'api/admin/saas-requests/<int:pk>/',
        views.api_admin_saas_request_action,
        name='api_admin_saas_request_action',
    ),

    # ── API JSON ──────────────────────────────────────────────────────────
    path('api/productos/', views.api_productos, name='api_productos'),
    path('api/home-merchandising/', views.api_home_merchandising, name='api_home_merchandising'),
    path('api/search/suggest/', views.api_search_suggest, name='api_search_suggest'),
    path('api/asistente/', views.api_asistente, name='api_asistente'),

    # ── Applications (admin approval) ────────────────────────────────────
    path('panel/applications/', views.admin_applications_view, name='admin_applications'),
    path('panel/applications/<int:pk>/approve/', views.approve_application_view, name='approve_application'),
    path('panel/applications/<int:pk>/reject/', views.reject_application_view, name='reject_application'),
    path('admin/applications/', views.admin_applications_view),
    path('admin/applications/<int:pk>/approve/', views.approve_application_view),
    path('admin/applications/<int:pk>/reject/', views.reject_application_view),
    path('pending-approval/', views.pending_approval_view, name='pending_approval'),
]
