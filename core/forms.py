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
