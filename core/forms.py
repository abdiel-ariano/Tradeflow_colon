"""
=============================================================================
TRADEFLOW COLÓN — core/forms.py  (v2 — ERD Completo)
=============================================================================
"""
from django import forms
from .models import Company, Category, Product, Inventory, Address, Order, OrderItem


class CompanyForm(forms.ModelForm):
    class Meta:
        model  = Company
        fields = ['name', 'ruc', 'address_text', 'is_verified']
        widgets = {
            'name':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la empresa'}),
            'ruc':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUC'}),
            'address_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_verified':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductForm(forms.ModelForm):
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
    """
    Formulario de producto para el portal vendedor (sin selector de empresa).
    La empresa se asigna en la vista según la compañía del usuario.
    """

    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'sku', 'unit_price', 'currency', 'image', 'is_active']
        widgets = {
            'category':    forms.Select(attrs={'class': 'tf-input'}),
            'name':        forms.TextInput(attrs={'class': 'tf-input', 'placeholder': 'Nombre del producto'}),
            'description': forms.Textarea(attrs={'class': 'tf-input', 'rows': 4, 'placeholder': 'Descripción'}),
            'sku':         forms.TextInput(attrs={'class': 'tf-input', 'placeholder': 'SKU (opcional)'}),
            'unit_price':  forms.NumberInput(attrs={'class': 'tf-input', 'step': '0.01', 'min': '0'}),
            'currency':    forms.Select(attrs={'class': 'tf-input'}),
            'image':       forms.ClearableFileInput(attrs={'class': 'tf-input'}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SellerInventoryForm(forms.ModelForm):
    """
    Campos de inventario editables por el vendedor (stock y umbral de alerta).
    """

    class Meta:
        model = Inventory
        fields = ['stock_qty', 'low_stock_alert']
        widgets = {
            'stock_qty':       forms.NumberInput(attrs={'class': 'tf-input', 'min': '0'}),
            'low_stock_alert': forms.NumberInput(attrs={'class': 'tf-input', 'min': '0'}),
        }


class InventoryForm(forms.ModelForm):
    class Meta:
        model  = Inventory
        fields = ['stock_qty', 'reserved_qty', 'low_stock_alert']
        widgets = {
            'stock_qty':       forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reserved_qty':    forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'low_stock_alert': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class OrderForm(forms.ModelForm):
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
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Buscar por número o comprador...'})
    )
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Estado: Todos')] + Order.STATUS_CHOICES,
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
    """Registro de nuevo transportista (revisión admin)."""

    nombre_completo = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'tf-input'}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'tf-input'}))
    telefono = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'tf-input'}))
    empresa_nombre = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'tf-input'}))
    licencia = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'tf-input'}))
    vehiculo_tipo = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'tf-input'}))
    vehiculo_placa = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'tf-input'}))
    cobertura_descripcion = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'tf-input', 'rows': 3}),
    )
    tarifa_base = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'tf-input', 'step': '0.01', 'min': '0'}),
    )
    foto_licencia = forms.ImageField(required=False)
    acepta_terminos = forms.BooleanField(
        required=True,
        label='Acepto los términos y condiciones de TradeFlow Colón',
    )
