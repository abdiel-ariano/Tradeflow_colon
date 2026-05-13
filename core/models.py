"""
=============================================================================
TRADEFLOW COLÓN — core/models.py  (v2 — ERD Completo)
=============================================================================
Tablas implementadas (mapeadas exactamente al ERD del PDF):
  UserProfile  → extiende el User de Django con rol y teléfono
  Company      → empresa vendedora de la Zona Libre
  Category     → categoría de producto
  Product      → producto del catálogo
  Inventory    → stock por producto (1-a-1 con Product)
  Address      → dirección de envío del comprador
  Order        → cabecera de la orden
  OrderItem    → línea de detalle (producto + cantidad + precio snapshot)
  Payment      → pago asociado a una orden
  Shipment     → envío asociado a una orden
  Document     → documentos generados (factura, packing list, etc.)
  Cotizacion   → solicitud formal de precios (RFQ) buyer → empresa
  CotizacionItem → líneas de cotización con cantidad y precio ofertado
  python manage.py makemigrations
  python manage.py migrate
  python manage.py createsuperuser
=============================================================================
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


# =============================================================================
# PERFIL DE USUARIO
# =============================================================================

class UserProfile(models.Model):
    """
    Extiende el User de Django con campos extras del ERD.
    Relación 1-a-1 con User (se crea automáticamente al crear un User desde admin).
    """
    ROLE_CHOICES = [
        ('buyer',  'Comprador'),
        ('seller', 'Vendedor'),
        ('admin',  'Administrador'),
    ]

    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone  = models.CharField(max_length=30, blank=True, verbose_name='Teléfono')
    role   = models.CharField(max_length=10, choices=ROLE_CHOICES, default='buyer', verbose_name='Rol')

    class Meta:
        verbose_name        = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]'


# =============================================================================
# EMPRESA (COMPANY)
# =============================================================================

class Company(models.Model):
    """
    Empresa vendedora de la Zona Libre de Colón.
    Un Product pertenece a una Company.
    El campo owner identifica al usuario vendedor responsable del portal Mi Tienda.
    """
    name         = models.CharField(max_length=200, verbose_name='Nombre de empresa')
    ruc          = models.CharField(max_length=50, blank=True, verbose_name='RUC / Registro')
    address_text = models.TextField(blank=True, verbose_name='Dirección')
    is_verified  = models.BooleanField(default=False, verbose_name='¿Verificada?')
    owner        = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_companies',
        verbose_name='Propietario (vendedor)',
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering            = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# CATEGORÍA
# =============================================================================

class Category(models.Model):
    """Categoría de productos."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')

    class Meta:
        verbose_name        = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering            = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# PRODUCTO
# =============================================================================

class Product(models.Model):
    """
    Producto del catálogo.
    Pertenece a una Company y a una Category.
    Tiene un Inventory relacionado (1-a-1).
    """
    CURRENCY_CHOICES = [
        ('USD', 'Dólar estadounidense (USD)'),
        ('PAB', 'Balboa panameño (PAB)'),
    ]

    company     = models.ForeignKey(
        Company, on_delete=models.PROTECT,
        related_name='products', verbose_name='Empresa'
    )
    category    = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products', verbose_name='Categoría'
    )
    name        = models.CharField(max_length=200, verbose_name='Nombre del producto')
    description = models.TextField(blank=True, verbose_name='Descripción')
    sku         = models.CharField(max_length=100, blank=True, verbose_name='SKU')
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio unitario')
    currency    = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    image       = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Imagen')
    is_active   = models.BooleanField(default=True, verbose_name='¿Activo?')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Producto'
        verbose_name_plural = 'Productos'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.currency} {self.unit_price}'

    @property
    def stock_qty(self):
        """Acceso rápido al stock disponible desde el inventario relacionado."""
        if hasattr(self, 'inventory'):
            return self.inventory.stock_qty
        return 0

    @property
    def available_qty(self):
        """Stock real disponible = stock_qty - reserved_qty."""
        if hasattr(self, 'inventory'):
            return max(0, self.inventory.stock_qty - self.inventory.reserved_qty)
        return 0


# =============================================================================
# INVENTARIO
# =============================================================================

class Inventory(models.Model):
    """
    Control de stock por producto.
    Relación 1-a-1 con Product (un producto tiene exactamente un inventario).
    """
    product         = models.OneToOneField(
        Product, on_delete=models.CASCADE,
        related_name='inventory', verbose_name='Producto'
    )
    stock_qty       = models.PositiveIntegerField(default=0, verbose_name='Stock total')
    reserved_qty    = models.PositiveIntegerField(default=0, verbose_name='Cantidad reservada')
    low_stock_alert = models.PositiveIntegerField(default=5, verbose_name='Alerta de stock bajo')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Inventario'
        verbose_name_plural = 'Inventarios'

    def __str__(self):
        return f'Inventario: {self.product.name} | Stock: {self.stock_qty}'

    @property
    def available(self):
        return max(0, self.stock_qty - self.reserved_qty)

    @property
    def is_low_stock(self):
        return self.available <= self.low_stock_alert

    def reserve(self, qty):
        """Reserva unidades al crear un pedido (no descuenta aún)."""
        if self.available >= qty:
            self.reserved_qty += qty
            self.save(update_fields=['reserved_qty', 'updated_at'])
            return True
        return False

    def confirm_sale(self, qty):
        """Descuenta stock definitivamente al confirmar pago."""
        self.stock_qty   = max(0, self.stock_qty - qty)
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['stock_qty', 'reserved_qty', 'updated_at'])

    def release_reservation(self, qty):
        """Libera reserva si se cancela la orden."""
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['reserved_qty', 'updated_at'])


# =============================================================================
# DIRECCIÓN
# =============================================================================

class Address(models.Model):
    """Dirección de envío de un comprador."""
    user        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='addresses', verbose_name='Usuario'
    )
    label       = models.CharField(max_length=100, blank=True, verbose_name='Etiqueta (ej: Casa, Oficina)')
    country     = models.CharField(max_length=100, default='Panamá', verbose_name='País')
    city        = models.CharField(max_length=100, verbose_name='Ciudad')
    line1       = models.CharField(max_length=255, verbose_name='Dirección línea 1')
    line2       = models.CharField(max_length=255, blank=True, verbose_name='Dirección línea 2')
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='Código postal')
    is_default  = models.BooleanField(default=False, verbose_name='¿Predeterminada?')

    class Meta:
        verbose_name        = 'Dirección'
        verbose_name_plural = 'Direcciones'

    def __str__(self):
        return f'{self.label or "Dirección"} — {self.city}, {self.country}'

    def save(self, *args, **kwargs):
        # Si se marca como predeterminada, quitar la marca de las demás del mismo usuario
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# =============================================================================
# ORDEN
# =============================================================================

class Order(models.Model):
    """
    Cabecera de una orden de compra.
    Un buyer (User) hace una Order con una o más OrderItems.
    """
    STATUS_CHOICES = [
        ('pending',   'Pendiente'),
        ('paid',      'Pagado'),
        ('packed',    'Empacado'),
        ('shipped',   'Enviado'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ]

    ORDER_TYPE_CHOICES = [
        ('b2c', 'Consumidor final (B2C)'),
        ('b2b', 'Empresa a empresa (B2B)'),
    ]

    buyer        = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='orders', verbose_name='Comprador'
    )
    ship_address = models.ForeignKey(
        Address, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders', verbose_name='Dirección de envío'
    )
    order_number  = models.CharField(
        max_length=30, unique=True, editable=False,
        verbose_name='Número de orden'
    )
    status        = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    order_type    = models.CharField(max_length=3, choices=ORDER_TYPE_CHOICES, default='b2c')
    subtotal      = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total         = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes         = models.TextField(blank=True, verbose_name='Notas')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Orden'
        verbose_name_plural = 'Órdenes'
        ordering            = ['-created_at']

    def save(self, *args, **kwargs):
        # Genera el número de orden automáticamente al crear
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number():
        """Formato: TF-YYYYMM-XXXX (ej: TF-202601-A3F2)"""
        now    = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'TF-{now.strftime("%Y%m")}-{suffix}'

    def __str__(self):
        return f'Orden {self.order_number} — {self.buyer.get_full_name() or self.buyer.username}'

    def recalculate_totals(self):
        """Recalcula subtotal y total sumando los OrderItems."""
        self.subtotal = sum(item.line_total for item in self.items.all())
        self.total    = self.subtotal + self.shipping_cost
        self.save(update_fields=['subtotal', 'total', 'updated_at'])

    def get_status_color(self):
        colors = {
            'pending':   'badge-warning',
            'paid':      'badge-info',
            'packed':    'badge-info',
            'shipped':   'badge-primary',
            'delivered': 'badge-success',
            'cancelled': 'badge-danger',
        }
        return colors.get(self.status, 'badge-secondary')


# =============================================================================
# ITEM DE ORDEN
# =============================================================================

class OrderItem(models.Model):
    """
    Línea de detalle: qué producto, cuánto y a qué precio (snapshot del momento).
    El precio se guarda como snapshot para que los cambios futuros no afecten
    órdenes históricas.
    """
    order              = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='items', verbose_name='Orden'
    )
    product            = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        verbose_name='Producto'
    )
    qty                = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_price_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name='Precio unitario (al momento de la venta)'
    )
    line_total         = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name        = 'Item de orden'
        verbose_name_plural = 'Items de orden'

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price_snapshot * self.qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.qty}x {self.product.name} en {self.order.order_number}'


# =============================================================================
# PAGO (PAYMENT)
# =============================================================================

class Payment(models.Model):
    """
    Registro del pago de una orden.
    Relación 1-a-1 con Order (una orden tiene un solo pago).
    """
    PROVIDER_CHOICES = [
        ('mock',  'Simulado (desarrollo)'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('bank',   'Transferencia bancaria'),
    ]

    STATUS_CHOICES = [
        ('pending',  'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('refunded', 'Reembolsado'),
    ]

    order    = models.OneToOneField(
        Order, on_delete=models.CASCADE,
        related_name='payment', verbose_name='Orden'
    )
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default='mock')
    status   = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    amount   = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    paid_at  = models.DateTimeField(null=True, blank=True)
    txn_ref  = models.CharField(max_length=200, blank=True, verbose_name='Referencia de transacción')

    class Meta:
        verbose_name        = 'Pago'
        verbose_name_plural = 'Pagos'

    def __str__(self):
        return f'Pago [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# ENVÍO (SHIPMENT)
# =============================================================================

class Shipment(models.Model):
    """Registro del envío físico de una orden."""
    STATUS_CHOICES = [
        ('label',      'Etiqueta generada'),
        ('in_transit', 'En tránsito'),
        ('delivered',  'Entregado'),
        ('returned',   'Devuelto'),
    ]

    order           = models.OneToOneField(
        Order, on_delete=models.CASCADE,
        related_name='shipment', verbose_name='Orden'
    )
    courier_name    = models.CharField(max_length=100, blank=True, verbose_name='Mensajería / Courier')
    tracking_number = models.CharField(max_length=200, blank=True, verbose_name='Número de rastreo')
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default='label')
    shipped_at      = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío')
    delivered_at    = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de entrega')

    class Meta:
        verbose_name        = 'Envío'
        verbose_name_plural = 'Envíos'

    def __str__(self):
        return f'Envío [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# DOCUMENTO (DOCUMENT)
# =============================================================================

class Document(models.Model):
    """
    Documentos asociados a una orden (factura, packing list, etc.).
    Una orden puede tener múltiples documentos.
    """
    DOC_TYPE_CHOICES = [
        ('invoice',      'Factura'),
        ('packing_list', 'Packing List'),
        ('other',        'Otro'),
    ]

    order      = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='documents', verbose_name='Orden'
    )
    doc_type   = models.CharField(max_length=15, choices=DOC_TYPE_CHOICES, default='invoice')
    doc_number = models.CharField(max_length=100, blank=True, verbose_name='Número de documento')
    file_path  = models.FileField(upload_to='documents/', blank=True, null=True, verbose_name='Archivo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Documento'
        verbose_name_plural = 'Documentos'

    def __str__(self):
        return f'{self.get_doc_type_display()} {self.doc_number} — {self.order.order_number}'


# =============================================================================
# COTIZACIÓN (solicitud formal de precios antes de ordenar)
# =============================================================================

class Cotizacion(models.Model):
    """
    Cotización: permite al comprador solicitar precio formal de uno o más
    productos a una empresa antes de confirmar la orden.
    """
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('respondida', 'Respondida'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]

    numero = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Número')
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cotizaciones',
        verbose_name='Comprador',
    )
    empresa = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='cotizaciones',
        verbose_name='Empresa',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado',
    )
    notas_buyer = models.TextField(blank=True, verbose_name='Notas del comprador')
    notas_seller = models.TextField(blank=True, verbose_name='Notas del vendedor')
    validez_dias = models.PositiveIntegerField(default=30, verbose_name='Validez (días)')
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizacion_origen',
        verbose_name='Orden generada',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cotización'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-created_at']

    @staticmethod
    def _generate_numero():
        """Formato COT-YYYYMM-XXXX (hex)."""
        now = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'COT-{now.strftime("%Y%m")}-{suffix}'

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generate_numero()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero


class CotizacionItem(models.Model):
    """Ítem de una cotización con cantidad solicitada y precio ofertado opcional."""

    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Cotización',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name='Producto',
    )
    cantidad_solicitada = models.PositiveIntegerField(verbose_name='Cantidad solicitada')
    precio_ofertado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio ofertado (unitario)',
    )
    notas = models.TextField(blank=True, verbose_name='Notas de línea')

    class Meta:
        verbose_name = 'Ítem de cotización'
        verbose_name_plural = 'Ítems de cotización'

    def __str__(self):
        return f'{self.cantidad_solicitada}× {self.product.name} ({self.cotizacion.numero})'

    @property
    def linea_total(self):
        """Subtotal de línea si ya hay precio ofertado."""
        if self.precio_ofertado is None:
            return None
        return self.precio_ofertado * self.cantidad_solicitada
