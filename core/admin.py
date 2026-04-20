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
    Address, Order, OrderItem, Payment, Shipment, Document
)


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
class CompanyAdmin(admin.ModelAdmin):
    list_display   = ['name', 'ruc', 'is_verified', 'created_at']
    list_filter    = ['is_verified']
    search_fields  = ['name', 'ruc']
    list_editable  = ['is_verified']
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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display   = ['name', 'company', 'category', 'unit_price', 'currency', 'is_active', 'stock_display']
    list_filter    = ['company', 'category', 'currency', 'is_active']
    search_fields  = ['name', 'sku']
    list_editable  = ['unit_price', 'is_active']
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


# =============================================================================
# PERSONALIZACIÓN DEL PANEL
# =============================================================================

admin.site.site_header = 'TradeFlow Colón — Administración'
admin.site.site_title  = 'TradeFlow Admin'
admin.site.index_title = 'Panel de Control'
