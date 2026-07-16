"""Django forms for CFZ catalog, seller portal, orders, and carriers.

ModelForms bind Company/Product/Inventory/Order fields for admin-style and
Mi Tienda editing. Carrier applications feed the Transportista review queue.
"""
from django import forms
from .models import Company, Category, Product, Inventory, Address, Order, OrderItem


class CompanyForm(forms.ModelForm):
    """Create or edit a CFZ seller company record."""

    class Meta:
        model  = Company
        fields = ['name', 'ruc', 'address_text', 'is_verified']
        widgets = {
            'name':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company name'}),
            'ruc':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUC'}),
            'address_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_verified':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductForm(forms.ModelForm):
    """Admin-style product form including company assignment."""

    class Meta:
        model  = Product
        fields = ['company', 'category', 'name', 'description', 'sku', 'unit_price', 'currency', 'image', 'is_active']
        widgets = {
            'company':     forms.Select(attrs={'class': 'form-control'}),
            'category':    forms.Select(attrs={'class': 'form-control'}),
            'name':        forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'sku':         forms.TextInput(attrs={'class': 'form-control'}),
            'unit_price':  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'currency':    forms.Select(attrs={'class': 'form-control'}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SellerProductForm(forms.ModelForm):
    """Seller-portal product form without a company selector.

    Views assign ``company`` from the logged-in seller's owned Company.
    """

    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'sku', 'unit_price', 'currency', 'image', 'is_active']
        widgets = {
            'category':    forms.Select(attrs={'class': 'tf-input'}),
            'name':        forms.TextInput(attrs={'class': 'tf-input', 'placeholder': 'Product name'}),
            'description': forms.Textarea(attrs={'class': 'tf-input', 'rows': 4, 'placeholder': 'Description'}),
            'sku':         forms.TextInput(attrs={'class': 'tf-input', 'placeholder': 'Product code (optional)'}),
            'unit_price':  forms.NumberInput(attrs={'class': 'tf-input', 'step': '0.01', 'min': '0'}),
            'currency':    forms.Select(attrs={'class': 'tf-input'}),
            'image':       forms.ClearableFileInput(attrs={'class': 'tf-input'}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SellerInventoryForm(forms.ModelForm):
    """Seller-editable stock total and low-stock alert threshold."""

    class Meta:
        model = Inventory
        fields = ['stock_qty', 'low_stock_alert']
        labels = {
            'stock_qty': 'Total stock',
            'low_stock_alert': 'Low stock alert',
        }
        widgets = {
            'stock_qty':       forms.NumberInput(attrs={'class': 'tf-input', 'min': '0'}),
            'low_stock_alert': forms.NumberInput(attrs={'class': 'tf-input', 'min': '0'}),
        }


class InventoryForm(forms.ModelForm):
    """Full inventory form including reserved quantity (ops/admin)."""

    class Meta:
        model  = Inventory
        fields = ['stock_qty', 'reserved_qty', 'low_stock_alert']
        widgets = {
            'stock_qty':       forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reserved_qty':    forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'low_stock_alert': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class OrderForm(forms.ModelForm):
    """Checkout/order header fields for type, ship-to, and freight."""

    class Meta:
        model  = Order
        fields = ['order_type', 'ship_address', 'shipping_cost', 'notes']
        widgets = {
            'order_type':    forms.Select(attrs={'class': 'form-control'}),
            'ship_address':  forms.Select(attrs={'class': 'form-control'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'notes':         forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class FiltroOrdenForm(forms.Form):
    """Filter seller/admin order lists by text, status, and date range."""

    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Search by number or buyer...'})
    )
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Status: All')] + Order.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'filter-input'})
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'})
    )


class AplicacionTransportistaForm(forms.Form):
    """Public carrier signup awaiting admin Transportista approval."""

    nombre_completo = forms.CharField(
        max_length=200,
        label='Full name',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'tf-input'}),
    )
    telefono = forms.CharField(
        max_length=30,
        label='Phone',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    empresa_nombre = forms.CharField(
        max_length=200,
        label='Company name',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    licencia = forms.CharField(
        max_length=100,
        label='License',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    vehiculo_tipo = forms.CharField(
        max_length=100,
        label='Vehicle type',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    vehiculo_placa = forms.CharField(
        max_length=30,
        label='License plate',
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    cobertura_descripcion = forms.CharField(
        label='Coverage description',
        widget=forms.Textarea(attrs={'class': 'tf-input', 'rows': 3}),
    )
    tarifa_base = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label='Base rate',
        widget=forms.NumberInput(attrs={'class': 'tf-input', 'step': '0.01', 'min': '0'}),
    )
    foto_licencia = forms.ImageField(required=False)
    acepta_terminos = forms.BooleanField(
        required=True,
        label='I accept the terms and conditions of TradeFlow Colón',
    )
