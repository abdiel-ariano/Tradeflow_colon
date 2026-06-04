"""
=============================================================================
TRADEFLOW COLÓN — core/admin.py  (v2 — ERD Completo)
=============================================================================
Registra todos los modelos del ERD en el panel de administración Django.
Acceso: http://127.0.0.1:8000/admin/
=============================================================================
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document,
    Cotizacion, CotizacionItem, HomePromoSection,
    TransportCarrier, UserApplication, Transportista, AsignacionTransporte,
)
from .enterprise_models import (
    AdCampaign,
    AdCreditAccount,
    ApiAuditLog,
    ApiKey,
    CompanyBillingUsage,
    CompanyPlanCheckout,
    CompanyPlanCommercialRequest,
    CompanyPredictiveSnapshot,
    CompanySubscription,
    EmailDeliveryLog,
    SubscriptionUpgradeLog,
    LogisticsDispatchQueue,
    LogisticsEvent,
    LogisticsWebhookConfig,
    SaasPlan,
)
from .utils.admin_permissions import user_is_tradeflow_admin


class TradeFlowModelAdmin(admin.ModelAdmin):
    """
    Permisos del Django Admin para operadores con rol ``admin`` + ``is_staff``.

    El panel custom (/dashboard/) usa UserProfile.role; el sitio /admin/ de Django
    exige permisos de modelo (view/change) — este admin los alinea.
    """

    def _tradeflow_admin_access(self, request):
        return user_is_tradeflow_admin(request.user)

    def has_module_permission(self, request):
        return self._tradeflow_admin_access(request)

    def has_view_permission(self, request, obj=None):
        return self._tradeflow_admin_access(request)

    def has_add_permission(self, request):
        return self._tradeflow_admin_access(request)

    def has_change_permission(self, request, obj=None):
        return self._tradeflow_admin_access(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# =============================================================================
# PERFIL INLINE (aparece dentro del detalle de User)
# =============================================================================

class UserProfileInline(admin.StackedInline):
    model          = UserProfile
    can_delete     = False
    verbose_name_plural = 'Perfil'
    fields         = ['phone', 'role']


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


# Re-registrar User con el inline de perfil
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# =============================================================================
# COMPANY
# =============================================================================

@admin.register(Company)
class CompanyAdmin(TradeFlowModelAdmin):
    """
    Administración de empresas; incluye propietario vendedor para el portal Mi Tienda.
    """
    list_display   = ['name', 'ruc', 'owner', 'is_verified', 'is_featured', 'created_at']
    list_filter    = ['is_verified', 'is_featured']
    search_fields  = ['name', 'ruc', 'owner__username', 'owner__email']
    list_editable  = ['is_verified']
    raw_id_fields  = ['owner']
    list_per_page  = 25


# =============================================================================
# CATEGORY
# =============================================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name']
    search_fields = ['name']


# =============================================================================
# PRODUCT + INVENTORY INLINE
# =============================================================================

class InventoryInline(admin.StackedInline):
    model      = Inventory
    can_delete = False
    verbose_name_plural = 'Inventario'
    fields     = ['stock_qty', 'reserved_qty', 'low_stock_alert']
    readonly_fields = ['updated_at']

    # Auto-crear Inventory si no existe al abrir el producto
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs

    def has_add_permission(self, request, obj=None):
        # Solo 1 inventario por producto
        if obj and hasattr(obj, 'inventory'):
            return False
        return True


@admin.register(HomePromoSection)
class HomePromoSectionAdmin(admin.ModelAdmin):
    list_display = ['slug', 'section_type', 'title_es', 'is_active', 'sort_order', 'starts_at', 'ends_at']
    list_filter = ['section_type', 'is_active']
    search_fields = ['slug', 'title_es', 'title_en']
    filter_horizontal = ['products', 'companies', 'categories']
    ordering = ['sort_order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display   = [
        'name', 'company', 'unit_price', 'promo_price', 'currency',
        'is_active', 'is_featured', 'is_bestseller', 'stock_display',
    ]
    list_filter    = ['company', 'category', 'currency', 'is_active', 'is_featured', 'is_bestseller']
    search_fields  = ['name', 'sku']
    list_editable  = ['unit_price', 'is_active', 'is_featured']
    inlines        = [InventoryInline]
    list_per_page  = 25

    def stock_display(self, obj):
        if hasattr(obj, 'inventory'):
            return f'{obj.inventory.available} disponibles'
        return '—'
    stock_display.short_description = 'Stock disponible'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display   = ['product', 'stock_qty', 'reserved_qty', 'available_display', 'is_low_stock', 'updated_at']
    list_filter    = []
    search_fields  = ['product__name']
    readonly_fields = ['updated_at']
    list_per_page  = 25

    def available_display(self, obj):
        return obj.available
    available_display.short_description = 'Disponible'

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Stock bajo'


# =============================================================================
# ADDRESS
# =============================================================================

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display  = ['user', 'label', 'city', 'country', 'is_default']
    list_filter   = ['country', 'is_default']
    search_fields = ['user__username', 'user__email', 'city', 'line1']


# =============================================================================
# ORDER + ITEMS INLINE
# =============================================================================

class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    readonly_fields = ['line_total']
    fields          = ['product', 'qty', 'unit_price_snapshot', 'line_total']


class PaymentInline(admin.StackedInline):
    model      = Payment
    can_delete = False
    extra      = 0
    readonly_fields = ['paid_at']
    fields     = ['provider', 'status', 'amount', 'currency', 'paid_at', 'txn_ref']


class ShipmentInline(admin.StackedInline):
    model      = Shipment
    can_delete = False
    extra      = 0
    fields     = ['courier_name', 'tracking_number', 'status', 'shipped_at', 'delivered_at']


class DocumentInline(admin.TabularInline):
    model  = Document
    extra  = 0
    fields = ['doc_type', 'doc_number', 'file_path']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = ['order_number', 'buyer', 'order_type', 'status', 'total', 'created_at']
    list_filter    = ['status', 'order_type']
    search_fields  = ['order_number', 'buyer__username', 'buyer__email']
    readonly_fields = ['order_number', 'subtotal', 'total', 'created_at', 'updated_at']
    inlines        = [OrderItemInline, PaymentInline, ShipmentInline, DocumentInline]
    list_per_page  = 25


# =============================================================================
# PAYMENT, SHIPMENT, DOCUMENT (vistas independientes)
# =============================================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['order', 'provider', 'status', 'amount', 'currency', 'paid_at']
    list_filter   = ['provider', 'status']
    search_fields = ['order__order_number', 'txn_ref']
    readonly_fields = ['paid_at']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display  = ['order', 'courier_name', 'tracking_number', 'status', 'shipped_at']
    list_filter   = ['status']
    search_fields = ['order__order_number', 'tracking_number']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ['order', 'doc_type', 'doc_number', 'created_at']
    list_filter   = ['doc_type']
    search_fields = ['order__order_number', 'doc_number']


class CotizacionItemInline(admin.TabularInline):
    model = CotizacionItem
    extra = 0
    raw_id_fields = ['product']


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    """
    Administración de cotizaciones RFQ entre compradores y empresas.
    """
    list_display = ['numero', 'buyer', 'empresa', 'estado', 'es_automatica', 'created_at', 'order']
    list_filter = ['estado', 'es_automatica', 'created_at']
    search_fields = ['numero', 'buyer__username', 'empresa__name', 'lote']
    readonly_fields = ['numero', 'created_at', 'updated_at']
    inlines = [CotizacionItemInline]


@admin.register(TransportCarrier)
class TransportCarrierAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'transport_mode', 'base_shipping_cost', 'sort_order', 'is_active']
    list_editable = ['sort_order', 'is_active']
    prepopulated_fields = {'code': ('name',)}


@admin.register(Transportista)
class TransportistaAdmin(admin.ModelAdmin):
    list_display = ['empresa_nombre', 'email_contacto', 'estado', 'activo', 'tarifa_base']
    list_filter = ['estado', 'activo']


@admin.register(AsignacionTransporte)
class AsignacionTransporteAdmin(admin.ModelAdmin):
    list_display = ['order', 'transportista', 'estado', 'costo_transporte']


@admin.register(UserApplication)
class UserApplicationAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'role', 'status', 'created_at']
    list_filter = ['status', 'role']
    search_fields = ['full_name', 'email', 'company_name']
    readonly_fields = ['review_token', 'created_at', 'reviewed_at']
    actions = ['aprobar_solicitudes', 'rechazar_solicitudes']

    def save_model(self, request, obj, form, change):
        """Editing the status to approved/rejected activates + notifies the user."""
        from .utils.application_review import aprobar_solicitud, rechazar_solicitud

        old_status = None
        if change and obj.pk:
            old_status = (
                UserApplication.objects.filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.status == 'approved' and old_status != 'approved':
            aprobar_solicitud(obj, notificar=True)
            self.message_user(request, f'{obj.email}: approved, account activated and notified.')
        elif obj.status == 'rejected' and old_status != 'rejected':
            rechazar_solicitud(obj, notificar=True)
            self.message_user(request, f'{obj.email}: rejected and notified.')

    @admin.action(description='Approve selected applications (activate + email)')
    def aprobar_solicitudes(self, request, queryset):
        from .utils.application_review import aprobar_solicitud

        count = 0
        for app in queryset:
            if app.status != 'approved':
                aprobar_solicitud(app, notificar=True)
                count += 1
        self.message_user(request, f'{count} application(s) approved and notified.')

    @admin.action(description='Reject selected applications (email)')
    def rechazar_solicitudes(self, request, queryset):
        from .utils.application_review import rechazar_solicitud

        count = 0
        for app in queryset:
            if app.status != 'rejected':
                rechazar_solicitud(app, notificar=True)
                count += 1
        self.message_user(request, f'{count} application(s) rejected and notified.')


# =============================================================================
# PERSONALIZACIÓN DEL PANEL
# =============================================================================

@admin.register(SaasPlan)
class SaasPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'monthly_volume_limit_usd', 'predictive_ai', 'sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'status', 'current_period_end']
    list_filter = ['status', 'plan']


@admin.register(CompanyBillingUsage)
class CompanyBillingUsageAdmin(admin.ModelAdmin):
    list_display = ['company', 'period_year', 'period_month', 'volume_usd', 'orders_count']


@admin.register(SubscriptionUpgradeLog)
class SubscriptionUpgradeLogAdmin(admin.ModelAdmin):
    list_display = ['company', 'from_plan', 'to_plan', 'source', 'activated_at']
    list_filter = ['source']
    readonly_fields = ['company', 'from_plan', 'to_plan', 'source', 'activated_at', 'notes']


@admin.register(CompanyPlanCheckout)
class CompanyPlanCheckoutAdmin(admin.ModelAdmin):
    list_display = ['company', 'target_plan', 'amount_usd', 'status', 'provider', 'created_at', 'paid_at']
    list_filter = ['status', 'provider', 'target_plan']
    search_fields = ['company__name', 'txn_ref']


@admin.register(CompanyPlanCommercialRequest)
class CompanyPlanCommercialRequestAdmin(admin.ModelAdmin):
    list_display = ['company', 'requested_plan', 'status', 'contact_email', 'created_at']
    list_filter = ['status', 'requested_plan']
    search_fields = ['contact_email', 'contact_name', 'company__name']


@admin.register(CompanyPredictiveSnapshot)
class CompanyPredictiveSnapshotAdmin(admin.ModelAdmin):
    list_display = ['company', 'period_key', 'computed_at']
    readonly_fields = ['company', 'period_key', 'payload', 'computed_at']


@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'product', 'placement', 'is_active', 'ends_at']


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'key_prefix', 'is_active', 'last_used_at']
    readonly_fields = ['key_hash', 'key_prefix']


@admin.register(LogisticsWebhookConfig)
class LogisticsWebhookAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'endpoint_url', 'is_active']


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'email_type', 'recipient', 'subject', 'status']
    list_filter = ['status', 'email_type']
    search_fields = ['recipient', 'subject', 'error_message']
    readonly_fields = [
        'email_type', 'recipient', 'subject', 'status',
        'error_message', 'backend', 'created_at',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False


admin.site.site_header = 'TradeFlow Colón — Administración'
admin.site.site_title  = 'TradeFlow Admin'
admin.site.index_title = 'Panel de Control'
