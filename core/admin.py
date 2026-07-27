"""Django admin registration for TradeFlow Colón ERD and enterprise models.

Exposes CFZ sellers, catalog, orders, RFQs, carriers, SaaS billing, and
email logs at /admin/. TradeFlowModelAdmin aligns staff role with model perms.
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


class TradeFlowPermissionMixin:
    """Align Django Admin permissions with TradeFlow operator roles.

    Authenticated staff with the TradeFlow ``admin`` profile can inspect and
    maintain registered resources. The configured demo is read-only by default
    and receives full CRUD access only while Expo mode is explicitly enabled.
    """

    def _tradeflow_admin_access(self, request):
        """Return whether the request user is a TradeFlow administrator."""
        return user_is_tradeflow_admin(request.user)

    def _tradeflow_read_only(self, request):
        """Return whether the current operator is the read-only SaaS demo."""
        from .utils.saas_demo import user_is_read_only_saas_demo

        return user_is_read_only_saas_demo(request.user)

    def _tradeflow_expo_demo(self, request):
        """Return whether the demo operator has writable Expo access."""
        from .utils.saas_demo import user_is_expo_demo_admin

        return user_is_expo_demo_admin(request.user)

    def has_module_permission(self, request):
        """Allow the application index for TradeFlow administrators."""
        return self._tradeflow_admin_access(request)

    def has_view_permission(self, request, obj=None):
        """Allow object lists and details for TradeFlow administrators."""
        return self._tradeflow_admin_access(request)

    def has_add_permission(self, request):
        """Allow creates except for the configured demonstration account."""
        return (
            self._tradeflow_admin_access(request)
            and not self._tradeflow_read_only(request)
        )

    def has_change_permission(self, request, obj=None):
        """Allow edits except for the configured demonstration account."""
        return (
            self._tradeflow_admin_access(request)
            and not self._tradeflow_read_only(request)
        )

    def has_delete_permission(self, request, obj=None):
        """Allow deletion to superusers or the explicitly enabled Expo demo."""
        can_delete = (
            request.user.is_superuser
            or self._tradeflow_expo_demo(request)
        )
        return can_delete and not self._tradeflow_read_only(request)


class TradeFlowModelAdmin(TradeFlowPermissionMixin, admin.ModelAdmin):
    """Base ModelAdmin with consistent TradeFlow operational defaults."""

    empty_value_display = '—'
    list_per_page = 30
    save_on_top = True


class TradeFlowReadOnlyAdmin(TradeFlowModelAdmin):
    """Expose generated audit records without allowing manual mutation."""

    def has_add_permission(self, request):
        """Disallow manual inserts for generated operational records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Keep generated operational records immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Keep generated operational records available for auditing."""
        return False


# =============================================================================
# USER PROFILE INLINE
# =============================================================================

class UserProfileInline(admin.StackedInline):
    """Show role/phone on the Django User change form."""

    model          = UserProfile
    can_delete     = False
    verbose_name_plural = 'Perfil'
    fields         = ['phone', 'role']


class UserAdmin(TradeFlowPermissionMixin, BaseUserAdmin):
    """Manage TradeFlow accounts without exposing superuser escalation."""

    inlines = (UserProfileInline,)

    def has_change_permission(self, request, obj=None):
        """Protect Django superusers from non-superuser operators."""
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Protect Django superusers from deletion by Expo operators."""
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        """Hide privilege-escalation fields from platform operators."""
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets

        protected_fields = {'is_superuser', 'groups', 'user_permissions'}
        safe_fieldsets = []
        for title, options in fieldsets:
            fields = tuple(
                field
                for field in options.get('fields', ())
                if field not in protected_fields
            )
            safe_options = {**options, 'fields': fields}
            safe_fieldsets.append((title, safe_options))
        return tuple(safe_fieldsets)


# Re-register User with the profile inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# =============================================================================
# COMPANY
# =============================================================================

@admin.register(Company)
class CompanyAdmin(TradeFlowModelAdmin):
    """Manage CFZ seller companies and Mi Tienda owners."""

    list_display   = ['name', 'ruc', 'owner', 'is_verified', 'is_featured', 'created_at']
    list_filter    = ['is_verified', 'is_featured']
    search_fields  = ['name', 'ruc', 'owner__username', 'owner__email']
    list_editable  = ['is_verified']
    raw_id_fields  = ['owner']
    fields         = [
        'name', 'logo', 'ruc', 'address_text', 'owner', 'is_verified', 'is_featured',
        'carousel_priority', 'tagline_es', 'tagline_en', 'order_confirm_hours',
        'latitud', 'longitud',
    ]
    list_per_page  = 25


# =============================================================================
# CATEGORY
# =============================================================================

@admin.register(Category)
class CategoryAdmin(TradeFlowModelAdmin):
    """Manage catalog categories."""

    list_display  = ['name']
    search_fields = ['name']


# =============================================================================
# PRODUCT + INVENTORY INLINE
# =============================================================================

class InventoryInline(admin.StackedInline):
    """Edit the single Inventory row from the Product change page."""

    model      = Inventory
    can_delete = False
    verbose_name_plural = 'Inventario'
    fields     = ['stock_qty', 'reserved_qty', 'low_stock_alert']
    readonly_fields = ['updated_at']

    def get_queryset(self, request):
        """Return the standard inventory queryset for the inline."""
        qs = super().get_queryset(request)
        return qs

    def has_add_permission(self, request, obj=None):
        """Block a second inventory when the product already has one."""
        if obj and hasattr(obj, 'inventory'):
            return False
        return True


@admin.register(HomePromoSection)
class HomePromoSectionAdmin(TradeFlowModelAdmin):
    """Schedule home CMS promo sections without redeploy."""

    list_display = ['slug', 'section_type', 'title_es', 'is_active', 'sort_order', 'starts_at', 'ends_at']
    list_filter = ['section_type', 'is_active']
    search_fields = ['slug', 'title_es', 'title_en']
    filter_horizontal = ['products', 'companies', 'categories']
    ordering = ['sort_order']


@admin.register(Product)
class ProductAdmin(TradeFlowModelAdmin):
    """Manage catalog SKUs with inline stock."""

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
        """Show available units for the list column."""
        if hasattr(obj, 'inventory'):
            return f'{obj.inventory.available} disponibles'
        return '—'
    stock_display.short_description = 'Stock disponible'


@admin.register(Inventory)
class InventoryAdmin(TradeFlowModelAdmin):
    """Manage per-SKU stock, reservations, and low-stock flags."""

    list_display   = ['product', 'stock_qty', 'reserved_qty', 'available_display', 'is_low_stock', 'updated_at']
    list_filter    = []
    search_fields  = ['product__name']
    readonly_fields = ['updated_at']
    list_per_page  = 25

    def available_display(self, obj):
        """Expose Inventory.available on the changelist."""
        return obj.available
    available_display.short_description = 'Disponible'

    def is_low_stock(self, obj):
        """Boolean column for the low-stock threshold."""
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Stock bajo'


# =============================================================================
# ADDRESS
# =============================================================================

@admin.register(Address)
class AddressAdmin(TradeFlowModelAdmin):
    """Manage buyer shipping addresses."""

    list_display  = ['user', 'label', 'city', 'country', 'is_default']
    list_filter   = ['country', 'is_default']
    search_fields = ['user__username', 'user__email', 'city', 'line1']


# =============================================================================
# ORDER + ITEMS INLINE
# =============================================================================

class OrderItemInline(admin.TabularInline):
    """Order line items with computed line totals."""

    model           = OrderItem
    extra           = 0
    readonly_fields = ['line_total']
    fields          = ['product', 'qty', 'unit_price_snapshot', 'line_total']


class PaymentInline(admin.StackedInline):
    """Payment status nested on the order change form."""

    model      = Payment
    can_delete = False
    extra      = 0
    readonly_fields = ['paid_at']
    fields     = ['provider', 'status', 'amount', 'currency', 'paid_at', 'txn_ref']


class ShipmentInline(admin.StackedInline):
    """Shipment tracking nested on the order change form."""

    model      = Shipment
    can_delete = False
    extra      = 0
    fields     = ['courier_name', 'tracking_number', 'status', 'shipped_at', 'delivered_at']


class DocumentInline(admin.TabularInline):
    """Trade documents attached to an order."""

    model  = Document
    extra  = 0
    fields = ['doc_type', 'doc_number', 'file_path']


@admin.register(Order)
class OrderAdmin(TradeFlowModelAdmin):
    """Manage buyer orders with payment, shipment, and document inlines."""

    list_display   = ['order_number', 'buyer', 'order_type', 'status', 'total', 'created_at']
    list_filter    = ['status', 'order_type']
    search_fields  = ['order_number', 'buyer__username', 'buyer__email']
    readonly_fields = ['order_number', 'subtotal', 'total', 'created_at', 'updated_at']
    inlines        = [OrderItemInline, PaymentInline, ShipmentInline, DocumentInline]
    list_per_page  = 25


# =============================================================================
# PAYMENT, SHIPMENT, DOCUMENT (standalone)
# =============================================================================

@admin.register(Payment)
class PaymentAdmin(TradeFlowModelAdmin):
    """Standalone payment list for reconciliation."""

    list_display  = ['order', 'provider', 'status', 'amount', 'currency', 'paid_at']
    list_filter   = ['provider', 'status']
    search_fields = ['order__order_number', 'txn_ref']
    readonly_fields = ['paid_at']


@admin.register(Shipment)
class ShipmentAdmin(TradeFlowModelAdmin):
    """Standalone shipment tracking list."""

    list_display  = ['order', 'courier_name', 'tracking_number', 'status', 'shipped_at']
    list_filter   = ['status']
    search_fields = ['order__order_number', 'tracking_number']


@admin.register(Document)
class DocumentAdmin(TradeFlowModelAdmin):
    """Standalone trade-document list."""

    list_display  = ['order', 'doc_type', 'doc_number', 'created_at']
    list_filter   = ['doc_type']
    search_fields = ['order__order_number', 'doc_number']


class CotizacionItemInline(admin.TabularInline):
    """RFQ line items on the quote change form."""

    model = CotizacionItem
    extra = 0
    raw_id_fields = ['product']


@admin.register(Cotizacion)
class CotizacionAdmin(TradeFlowModelAdmin):
    """Manage buyer↔seller RFQ quotes and linked orders."""

    list_display = ['numero', 'buyer', 'empresa', 'estado', 'es_automatica', 'created_at', 'order']
    list_filter = ['estado', 'es_automatica', 'created_at']
    search_fields = ['numero', 'buyer__username', 'empresa__name', 'lote']
    readonly_fields = ['numero', 'created_at', 'updated_at']
    inlines = [CotizacionItemInline]


@admin.register(TransportCarrier)
class TransportCarrierAdmin(TradeFlowModelAdmin):
    """Manage checkout carrier options and base freight."""

    list_display = ['name', 'code', 'transport_mode', 'base_shipping_cost', 'sort_order', 'is_active']
    list_editable = ['sort_order', 'is_active']
    prepopulated_fields = {'code': ('name',)}


@admin.register(Transportista)
class TransportistaAdmin(TradeFlowModelAdmin):
    """Review and activate registered last-mile carriers."""

    list_display = ['empresa_nombre', 'email_contacto', 'estado', 'activo', 'tarifa_base']
    list_filter = ['estado', 'activo']


@admin.register(AsignacionTransporte)
class AsignacionTransporteAdmin(TradeFlowModelAdmin):
    """View per-order carrier assignments."""

    list_display = ['order', 'transportista', 'estado', 'costo_transporte']


@admin.register(UserApplication)
class UserApplicationAdmin(TradeFlowModelAdmin):
    """Approve or reject buyer/seller access applications."""

    list_display = ['full_name', 'email', 'role', 'status', 'created_at']
    list_filter = ['status', 'role']
    search_fields = ['full_name', 'email', 'company_name']
    readonly_fields = ['review_token', 'created_at', 'reviewed_at']
    actions = ['aprobar_solicitudes', 'rechazar_solicitudes']

    def save_model(self, request, obj, form, change):
        """Activate and notify when status moves to approved/rejected."""
        from .utils.application_review import (
            aprobar_solicitud,
            mensaje_fallo_correo,
            rechazar_solicitud,
        )

        old_status = None
        if change and obj.pk:
            old_status = (
                UserApplication.objects.filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.status == 'approved' and old_status != 'approved':
            _, email_result = aprobar_solicitud(obj, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                self.message_user(request, f'{obj.email}: {warn}', level=30)
            else:
                self.message_user(request, f'{obj.email}: approved, account activated and notified.')
        elif obj.status == 'rejected' and old_status != 'rejected':
            _, email_result = rechazar_solicitud(obj, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                self.message_user(request, f'{obj.email}: {warn}', level=30)
            else:
                self.message_user(request, f'{obj.email}: rejected and notified.')

    @admin.action(description='Approve selected applications (activate + email)')
    def aprobar_solicitudes(self, request, queryset):
        """Bulk-approve applications and send activation email."""
        from .utils.application_review import aprobar_solicitud, mensaje_fallo_correo

        count = 0
        email_fail = 0
        for app in queryset:
            if app.status != 'approved':
                _, email_result = aprobar_solicitud(app, notificar=True)
                count += 1
                if mensaje_fallo_correo(email_result):
                    email_fail += 1
        msg = f'{count} application(s) approved.'
        if email_fail:
            msg += f' {email_fail} without email (check Gmail or Supabase).'
        self.message_user(request, msg)

    @admin.action(description='Reject selected applications (email)')
    def rechazar_solicitudes(self, request, queryset):
        """Bulk-reject applications and notify applicants."""
        from .utils.application_review import mensaje_fallo_correo, rechazar_solicitud

        count = 0
        email_fail = 0
        for app in queryset:
            if app.status != 'rejected':
                _, email_result = rechazar_solicitud(app, notificar=True)
                count += 1
                if mensaje_fallo_correo(email_result):
                    email_fail += 1
        msg = f'{count} application(s) rejected.'
        if email_fail:
            msg += f' {email_fail} without email (check Gmail or Supabase).'
        self.message_user(request, msg)


# =============================================================================
# ENTERPRISE / SAAS ADMIN
# =============================================================================

@admin.register(SaasPlan)
class SaasPlanAdmin(TradeFlowModelAdmin):
    """Manage SaaS plan catalog and feature flags."""

    list_display = ['name', 'slug', 'monthly_volume_limit_usd', 'predictive_ai', 'sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(TradeFlowModelAdmin):
    """View seller subscription status and period end."""

    list_display = ['company', 'plan', 'status', 'current_period_end']
    list_filter = ['status', 'plan']


@admin.register(CompanyBillingUsage)
class CompanyBillingUsageAdmin(TradeFlowModelAdmin):
    """Inspect monthly billable GMV per company."""

    list_display = ['company', 'period_year', 'period_month', 'volume_usd', 'orders_count']


@admin.register(SubscriptionUpgradeLog)
class SubscriptionUpgradeLogAdmin(TradeFlowReadOnlyAdmin):
    """Read-only history of plan upgrades."""

    list_display = ['company', 'from_plan', 'to_plan', 'source', 'activated_at']
    list_filter = ['source']
    readonly_fields = ['company', 'from_plan', 'to_plan', 'source', 'activated_at', 'notes']


@admin.register(CompanyPlanCheckout)
class CompanyPlanCheckoutAdmin(TradeFlowModelAdmin):
    """Review bank-transfer SaaS checkouts and activate plans.

    Approve runs ``approve_plan_checkout``; reject asks the seller to resubmit.
    """

    list_display = [
        'company', 'target_plan', 'amount_usd', 'status', 'provider',
        'transfer_reference', 'created_at', 'paid_at', 'reviewed_at',
    ]
    list_filter = ['status', 'provider', 'target_plan']
    search_fields = ['company__name', 'txn_ref', 'transfer_reference']
    readonly_fields = [
        'company', 'from_plan', 'target_plan', 'amount_usd', 'currency',
        'billing_label', 'created_at', 'paid_at', 'expires_at',
        'reviewed_at', 'reviewed_by',
    ]
    fields = [
        'company', 'from_plan', 'target_plan', 'amount_usd', 'currency',
        'billing_label', 'status', 'provider', 'txn_ref',
        'transfer_reference', 'seller_notes', 'proof_file',
        'review_notes', 'reviewed_at', 'reviewed_by',
        'created_at', 'paid_at', 'expires_at',
    ]
    actions = ['approve_selected_transfers', 'reject_selected_transfers']

    @admin.action(description='Approve bank transfer and activate plan')
    def approve_selected_transfers(self, request, queryset):
        """Approve pending checkouts and activate the target plan."""
        from core.utils.saas_billing import approve_plan_checkout

        ok = 0
        for checkout in queryset.filter(status='pending'):
            try:
                approve_plan_checkout(
                    checkout,
                    reviewed_by=request.user,
                    review_notes='admin_bulk_approve',
                )
                ok += 1
            except ValueError as exc:
                self.message_user(
                    request,
                    f'Checkout #{checkout.pk}: {exc}',
                    level='ERROR',
                )
        self.message_user(request, f'Approved {ok} checkout(s).')

    @admin.action(description='Reject bank transfer')
    def reject_selected_transfers(self, request, queryset):
        """Reject pending checkouts so the seller can resubmit proof."""
        from core.utils.saas_billing import reject_plan_checkout

        ok = 0
        for checkout in queryset.filter(status='pending'):
            try:
                reject_plan_checkout(
                    checkout,
                    reviewed_by=request.user,
                    review_notes='admin_bulk_reject',
                )
                ok += 1
            except ValueError as exc:
                self.message_user(
                    request,
                    f'Checkout #{checkout.pk}: {exc}',
                    level='ERROR',
                )
        self.message_user(request, f'Rejected {ok} checkout(s).')


@admin.register(CompanyPlanCommercialRequest)
class CompanyPlanCommercialRequestAdmin(TradeFlowModelAdmin):
    """Track Enterprise commercial plan requests."""

    list_display = ['company', 'requested_plan', 'status', 'contact_email', 'created_at']
    list_filter = ['status', 'requested_plan']
    search_fields = ['contact_email', 'contact_name', 'company__name']


@admin.register(CompanyPredictiveSnapshot)
class CompanyPredictiveSnapshotAdmin(TradeFlowModelAdmin):
    """Inspect cached Enterprise predictive payloads."""

    list_display = ['company', 'period_key', 'computed_at']
    readonly_fields = ['company', 'period_key', 'payload', 'computed_at']


@admin.register(AdCampaign)
class AdCampaignAdmin(TradeFlowModelAdmin):
    """Manage seller ad campaigns and placements."""

    list_display = ['name', 'company', 'product', 'placement', 'is_active', 'ends_at']


@admin.register(ApiKey)
class ApiKeyAdmin(TradeFlowModelAdmin):
    """Manage seller API keys (hash/prefix read-only)."""

    list_display = ['name', 'company', 'key_prefix', 'is_active', 'last_used_at']
    readonly_fields = ['key_hash', 'key_prefix']


@admin.register(LogisticsWebhookConfig)
class LogisticsWebhookAdmin(TradeFlowModelAdmin):
    """Manage logistics partner webhook endpoints."""

    list_display = ['name', 'company', 'endpoint_url', 'is_active']


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(TradeFlowReadOnlyAdmin):
    """Read-only transactional email delivery audit."""

    list_display = ['created_at', 'email_type', 'recipient', 'subject', 'status']
    list_filter = ['status', 'email_type']
    search_fields = ['recipient', 'subject', 'error_message']
    readonly_fields = [
        'email_type', 'recipient', 'subject', 'status',
        'error_message', 'backend', 'created_at',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """Disallow manual log inserts from the admin UI."""
        return False


@admin.register(AdCreditAccount)
class AdCreditAccountAdmin(TradeFlowModelAdmin):
    """Manage advertising credit balances by seller company."""

    list_display = ['company', 'balance', 'lifetime_spent', 'updated_at']
    search_fields = ['company__name', 'company__ruc']
    readonly_fields = ['lifetime_spent', 'updated_at']


@admin.register(LogisticsEvent)
class LogisticsEventAdmin(TradeFlowReadOnlyAdmin):
    """Inspect the immutable operational timeline of marketplace orders."""

    list_display = ['created_at', 'order', 'event_type', 'source', 'label']
    list_filter = ['event_type', 'source', 'created_at']
    search_fields = ['order__order_number', 'label']
    readonly_fields = [
        'order', 'event_type', 'label', 'payload', 'source', 'created_at',
    ]
    date_hierarchy = 'created_at'


@admin.register(LogisticsDispatchQueue)
class LogisticsDispatchQueueAdmin(TradeFlowReadOnlyAdmin):
    """Inspect webhook delivery attempts and logistics partner failures."""

    list_display = [
        'created_at', 'order', 'company', 'status', 'attempts', 'sent_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'order__order_number', 'company__name', 'last_error',
    ]
    readonly_fields = [
        'order', 'company', 'status', 'payload', 'signature', 'attempts',
        'last_error', 'created_at', 'sent_at',
    ]
    date_hierarchy = 'created_at'


@admin.register(ApiAuditLog)
class ApiAuditLogAdmin(TradeFlowReadOnlyAdmin):
    """Inspect seller API traffic for security and operational support."""

    list_display = [
        'created_at', 'company', 'method', 'path', 'status_code',
        'ip_address',
    ]
    list_filter = ['method', 'status_code', 'created_at']
    search_fields = [
        'company__name', 'api_key__name', 'path', 'ip_address',
    ]
    readonly_fields = [
        'api_key', 'company', 'method', 'path', 'status_code',
        'ip_address', 'created_at',
    ]
    date_hierarchy = 'created_at'


admin.site.site_header = 'TradeFlow Colón — Administración'
admin.site.site_title  = 'TradeFlow Admin'
admin.site.index_title = 'Panel de Control'
