"""Core ORM for TradeFlow Colón CFZ B2B marketplace.

Models cover seller companies, catalog inventory, buyer orders, RFQ quotes,
carriers, and auth tokens. Enterprise SaaS/ads/API tables re-export from
``enterprise_models`` so ``from core.models import …`` stays the single entry.
"""
from decimal import Decimal
import random
import secrets   # OWASP A02: CSPRNG for OTP (random.randint is predictable)

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


# =============================================================================
# USER PROFILE
# =============================================================================

class UserProfile(models.Model):
    """Extend Django User with CFZ marketplace role and buyer prefs.

    One-to-one with User. Role drives portal access (buyer/seller/admin/
    carrier). Cart snapshots power abandonment reminders; onboarding fields
    personalize the post-signup wizard.
    """
    ROLE_CHOICES = [
        ('buyer',  _('Buyer')),
        ('seller', _('Seller')),
        ('admin',  _('Administrator')),
        ('transportista', _('Carrier')),
    ]

    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone  = models.CharField(max_length=30, blank=True, verbose_name='Phone')
    role   = models.CharField(max_length=14, choices=ROLE_CHOICES, default='buyer', verbose_name='Role')
    email_verificado = models.BooleanField(
        default=False,
        verbose_name='Email verified',
    )
    token_verificacion = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text='UUID token for email verification',
    )
    codigo_verificacion_email = models.CharField(
        max_length=6,
        blank=True,
        verbose_name='Email verification code',
    )
    codigo_verificacion_expira = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Email code expiration',
    )
    cart_items_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Cart items (snapshot)',
        help_text='Units in session cart — used for abandonment reminders.',
    )
    cart_last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last cart activity',
    )
    cart_reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last cart reminder sent',
    )
    # Buyer onboarding (post-signup marketplace wizard).
    PURCHASE_INTENT_CHOICES = [
        ('business', _('Business purchase')),
        ('personal', _('Personal purchase')),
    ]
    purchase_intent = models.CharField(
        max_length=16,
        choices=PURCHASE_INTENT_CHOICES,
        blank=True,
        verbose_name='Purchase intent',
        help_text='Step 1 — wholesale vs personal shopping.',
    )
    preferred_categories = models.ManyToManyField(
        'Category',
        blank=True,
        related_name='buyer_profiles',
        verbose_name='Preferred categories',
        help_text='Step 2 — category interests for personalization.',
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        default=timezone.now,
        verbose_name='Buyer onboarding completed',
        help_text='Null = wizard pending for new buyer signups; default now for legacy/test profiles.',
    )

    class Meta:
        verbose_name        = 'User profile'
        verbose_name_plural = 'User profiles'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]'

    @property
    def email_verified(self) -> bool:
        """Expose English alias; value lives in ``email_verificado``."""
        return self.email_verificado

    @email_verified.setter
    def email_verified(self, value: bool) -> None:
        """Set the persisted Spanish-named verification flag."""
        self.email_verificado = value


# =============================================================================
# COMPANY (CFZ SELLER)
# =============================================================================

class Company(models.Model):
    """CFZ seller company storefront and verification record.

    Products belong to a Company. ``owner`` is the seller who runs Mi Tienda.
    Verification and featured flags drive trust badges and home carousels.
    """
    name         = models.CharField(max_length=200, verbose_name='Company name')
    ruc          = models.CharField(max_length=50, blank=True, verbose_name='RUC / Registration')
    address_text = models.TextField(blank=True, verbose_name='Address')
    is_verified  = models.BooleanField(default=False, verbose_name='Verified?')
    owner        = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_companies',
        verbose_name='Owner (seller)',
    )
    latitud      = models.FloatField(
        null=True,
        blank=True,
        default=9.3667,
        verbose_name='Latitude (CFZ)',
    )
    longitud     = models.FloatField(
        null=True,
        blank=True,
        default=-79.9000,
        verbose_name='Longitude (CFZ)',
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name='Featured on home',
    )
    carousel_priority = models.IntegerField(
        default=0,
        verbose_name='Carousel priority',
    )
    tagline_es = models.CharField(max_length=200, blank=True, verbose_name='Tagline (ES)')
    tagline_en = models.CharField(max_length=200, blank=True, verbose_name='Tagline (EN)')
    order_confirm_hours = models.PositiveIntegerField(
        default=48,
        verbose_name='Hours to confirm order',
        help_text='Deadline for the company to accept or reject a new order.',
    )
    logo = models.ImageField(
        upload_to='companies/logos/',
        blank=True,
        null=True,
        verbose_name='Logo',
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Company'
        verbose_name_plural = 'Companies'
        ordering            = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# CATEGORY
# =============================================================================

class Category(models.Model):
    """Catalog category for CFZ product browsing and filters."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')

    class Meta:
        verbose_name        = 'Category'
        verbose_name_plural = 'Categories'
        ordering            = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# HOME PROMO SECTIONS (LIGHT CMS)
# =============================================================================

class HomePromoSection(models.Model):
    """Configurable home landing block without redeploy.

    Ops schedule PreExpo/campaign rows (deals, spotlights, banners) via
    admin; merchandising resolves products from type and M2M links.
    """

    SECTION_TYPES = [
        ('product_row', _('View products')),
        ('product_carousel', _('View products')),
        ('category_spotlight', _('By category')),
        ('company_spotlight', _('By company')),
        ('seasonal_banner', _('Seasonal banner')),
        ('bestsellers', _('Bestsellers')),
        ('daily_deals', _('Daily deals')),
    ]

    slug = models.SlugField(max_length=80, unique=True)
    section_type = models.CharField(max_length=32, choices=SECTION_TYPES)
    title_es = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200, blank=True)
    subtitle_es = models.CharField(max_length=300, blank=True)
    subtitle_en = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_items = models.PositiveSmallIntegerField(default=8)
    config = models.JSONField(default=dict, blank=True)
    products = models.ManyToManyField(
        'Product',
        blank=True,
        related_name='promo_sections',
        verbose_name='Products',
    )
    companies = models.ManyToManyField(
        'Company',
        blank=True,
        related_name='promo_sections',
        verbose_name='Companies',
    )
    categories = models.ManyToManyField(
        'Category',
        blank=True,
        related_name='promo_sections',
        verbose_name='Categories',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Home promotional section')
        verbose_name_plural = _('Home promotional sections')
        ordering = ['sort_order', 'slug']

    def __str__(self):
        return self.title_es or self.slug

    def title_for_lang(self, lang_code: str) -> str:
        """Return ES/EN title for the active UI locale."""
        if lang_code == 'en' and self.title_en:
            return self.title_en
        return self.title_es

    def subtitle_for_lang(self, lang_code: str) -> str:
        """Return ES/EN subtitle for the active UI locale."""
        if lang_code == 'en' and self.subtitle_en:
            return self.subtitle_en
        return self.subtitle_es


# =============================================================================
# PRODUCT
# =============================================================================

class Product(models.Model):
    """CFZ catalog SKU owned by a seller Company.

    Linked 1:1 to Inventory for stock. Promo windows and merchandising
    priority shape public home/deals surfaces without changing list price.
    """
    CURRENCY_CHOICES = [
        ('USD', _('US Dollar (USD)')),
        ('PAB', _('Panamanian Balboa (PAB)')),
    ]

    company     = models.ForeignKey(
        Company, on_delete=models.PROTECT,
        related_name='products', verbose_name='Company'
    )
    category    = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products', verbose_name='Category'
    )
    name        = models.CharField(max_length=200, verbose_name='Product name')
    description = models.TextField(blank=True, verbose_name='Description')
    sku         = models.CharField(max_length=100, blank=True, verbose_name='Product code')
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Unit price')
    currency    = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    image       = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Image')
    is_active   = models.BooleanField(default=True, verbose_name='Active?')
    is_featured = models.BooleanField(default=False, verbose_name='Featured')
    is_bestseller = models.BooleanField(
        default=False,
        verbose_name='Bestseller (manual or recalculated)',
    )
    promo_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Promotional price',
    )
    promo_starts_at = models.DateTimeField(null=True, blank=True)
    promo_ends_at = models.DateTimeField(null=True, blank=True)
    merchandising_priority = models.IntegerField(default=0, verbose_name='Merchandising priority')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Product'
        verbose_name_plural = 'Products'
        ordering            = ['-merchandising_priority', 'name']

    def __str__(self):
        return f'{self.name} — {self.currency} {self.unit_price}'

    @property
    def is_on_promo_now(self) -> bool:
        """True when promo price is live and below list price."""
        if self.promo_price is None or self.promo_price >= self.unit_price:
            return False
        now = timezone.now()
        if self.promo_starts_at and now < self.promo_starts_at:
            return False
        if self.promo_ends_at and now > self.promo_ends_at:
            return False
        return True

    @property
    def display_price(self) -> Decimal:
        """Buyer-facing unit price (promo when active, else list)."""
        if self.is_on_promo_now:
            return self.promo_price
        return self.unit_price

    @property
    def discount_pct(self) -> int:
        """Whole-percent savings vs list while a promo is active."""
        if not self.is_on_promo_now or self.unit_price <= 0:
            return 0
        pct = (Decimal('1') - (self.promo_price / self.unit_price)) * Decimal('100')
        return int(pct.quantize(Decimal('1')))

    @property
    def stock_qty(self):
        """Total on-hand units from related Inventory (0 if missing)."""
        if hasattr(self, 'inventory'):
            return self.inventory.stock_qty
        return 0

    @property
    def available_qty(self):
        """Sellable units: stock minus reserved."""
        if hasattr(self, 'inventory'):
            return max(0, self.inventory.stock_qty - self.inventory.reserved_qty)
        return 0


# =============================================================================
# INVENTORY
# =============================================================================

class Inventory(models.Model):
    """Per-SKU stock control for CFZ warehouse availability.

    One-to-one with Product. Reservations hold units on order create;
    confirm_sale commits on payment; release restores cancelled holds.
    """
    product         = models.OneToOneField(
        Product, on_delete=models.CASCADE,
        related_name='inventory', verbose_name='Product'
    )
    stock_qty       = models.PositiveIntegerField(default=0, verbose_name='Stock total')
    reserved_qty    = models.PositiveIntegerField(default=0, verbose_name='Reserved quantity')
    low_stock_alert = models.PositiveIntegerField(default=5, verbose_name='Low stock alert')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Inventory'
        verbose_name_plural = 'Inventories'

    def __str__(self):
        return f'Inventario: {self.product.name} | Stock: {self.stock_qty}'

    @property
    def available(self):
        """Units free to sell after subtracting reservations."""
        return max(0, self.stock_qty - self.reserved_qty)

    @property
    def is_low_stock(self):
        """True when available stock is at or below the alert threshold."""
        return self.available <= self.low_stock_alert

    def reserve(self, qty):
        """Hold units when an order is placed (no stock decrement yet)."""
        if self.available >= qty:
            self.reserved_qty += qty
            self.save(update_fields=['reserved_qty', 'updated_at'])
            return True
        return False

    def confirm_sale(self, qty):
        """Commit reserved units after payment confirmation."""
        self.stock_qty   = max(0, self.stock_qty - qty)
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['stock_qty', 'reserved_qty', 'updated_at'])

    def release_reservation(self, qty):
        """Free a reservation when an order is cancelled."""
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['reserved_qty', 'updated_at'])


# =============================================================================
# ADDRESS
# =============================================================================

class Address(models.Model):
    """Buyer shipping address used at CFZ checkout."""
    user        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='addresses', verbose_name='User'
    )
    label       = models.CharField(max_length=100, blank=True, verbose_name='Label (e.g. Home, Office)')
    country     = models.CharField(max_length=100, default='Panamá', verbose_name='Country')
    city        = models.CharField(max_length=100, verbose_name='City')
    line1       = models.CharField(max_length=255, verbose_name='Address line 1')
    line2       = models.CharField(max_length=255, blank=True, verbose_name='Address line 2')
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='Postal code')
    is_default  = models.BooleanField(default=False, verbose_name='Default?')

    class Meta:
        verbose_name        = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f'{self.label or "Address"} — {self.city}, {self.country}'

    def save(self, *args, **kwargs):
        """Ensure only one default address per buyer."""
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# =============================================================================
# ORDER + ACCESS + CARRIERS
# =============================================================================

class TransportCarrier(models.Model):
    """Checkout carrier option for ZLC outbound logistics."""

    MODE_CHOICES = [
        ('maritime', _('Maritime')),
        ('air', _('Air')),
        ('terrestrial', _('Terrestrial')),
        ('mixed', _('Mixed')),
    ]

    name = models.CharField(max_length=120, verbose_name='Name')
    code = models.SlugField(max_length=40, unique=True, verbose_name='Code')
    transport_mode = models.CharField(
        max_length=12,
        choices=MODE_CHOICES,
        default='terrestrial',
        verbose_name='Transport mode',
    )
    description = models.TextField(blank=True, verbose_name='Description')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort order')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    base_shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Base shipping cost (USD)',
    )

    class Meta:
        verbose_name = 'Transport carrier'
        verbose_name_plural = 'Transport carriers'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class UserApplication(models.Model):
    """Access request for buyer/seller onboarding (PreExpo / investors)."""
    ROLE_CHOICES = [
        ('buyer', _('Buyer')),
        ('seller', _('Seller')),
    ]
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='access_applications',
        null=True,
        blank=True,
        verbose_name='User account',
    )
    full_name = models.CharField(max_length=120, verbose_name='Full name')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Phone')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='buyer')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Company')
    message = models.TextField(blank=True, verbose_name='Message')
    requested_plan_slug = models.CharField(
        max_length=40,
        blank=True,
        help_text='Requested SaaS plan (e.g. ecosistema_enterprise)',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    review_token = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Access request'
        verbose_name_plural = 'Access requests'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Assign a unique review token on first save."""
        if not self.review_token:
            self.review_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} — {self.email} ({self.get_status_display()})'


class Order(models.Model):
    """Buyer purchase header spanning CFZ B2B and B2C checkouts.

    Lines live in OrderItem. Seller confirmation gates fulfillment when a
    company must accept before packing; totals roll up from line snapshots.
    """
    STATUS_CHOICES = [
        ('awaiting_seller', _('Awaiting confirmation')),
        ('pending',   _('Pending')),
        ('paid',      _('Paid')),
        ('packed',    _('Packed')),
        ('shipped',   _('Shipped')),
        ('delivered', _('Delivered')),
        ('cancelled', _('Cancelled')),
    ]

    SELLER_CONFIRM_CHOICES = [
        ('pending', _('Pending')),
        ('accepted', _('Accepted')),
        ('rejected', _('Rejected')),
        ('expired', _('Expired')),
    ]

    ORDER_TYPE_CHOICES = [
        ('b2c', _('End consumer (B2C)')),
        ('b2b', _('Business to business (B2B)')),
    ]

    buyer        = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='orders', verbose_name='Buyer'
    )
    ship_address = models.ForeignKey(
        Address, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders', verbose_name='Shipping address'
    )
    order_number  = models.CharField(
        max_length=30, unique=True, editable=False,
        verbose_name='Order number'
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order_type    = models.CharField(max_length=3, choices=ORDER_TYPE_CHOICES, default='b2c')
    subtotal      = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total         = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes         = models.TextField(blank=True, verbose_name='Notes')
    transport_carrier = models.ForeignKey(
        TransportCarrier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Transport carrier',
    )
    buyer_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name='Buyer latitude',
    )
    buyer_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name='Buyer longitude',
    )
    buyer_location_verified_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Confirmed location',
    )
    confirming_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders_to_confirm',
        verbose_name='Confirming company',
    )
    seller_confirmation_status = models.CharField(
        max_length=12,
        choices=SELLER_CONFIRM_CHOICES,
        default='pending',
        verbose_name='Seller confirmation',
    )
    seller_confirm_by = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Confirm by',
    )
    tiempo_confirmacion_horas = models.PositiveIntegerField(
        default=24,
        verbose_name='Hours for company confirmation',
    )
    confirmado_por_empresa = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Company confirmation',
        help_text='True=accepted, False=rejected, None=pending',
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Order'
        verbose_name_plural = 'Orders'
        ordering            = ['-created_at']

    def save(self, *args, **kwargs):
        """Mint ``order_number`` on create if missing."""
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number():
        """Build TF-YYYYMM-XXXX identifiers for new orders."""
        now    = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'TF-{now.strftime("%Y%m")}-{suffix}'

    def __str__(self):
        return f'Orden {self.order_number} — {self.buyer.get_full_name() or self.buyer.username}'

    def recalculate_totals(self):
        """Recompute subtotal and total from OrderItem line totals."""
        self.subtotal = sum(item.line_total for item in self.items.all())
        self.total    = self.subtotal + self.shipping_cost
        self.save(update_fields=['subtotal', 'total', 'updated_at'])

    def get_status_color(self):
        """Map status to Bootstrap badge CSS class for dashboards."""
        colors = {
            'awaiting_seller': 'badge-warning',
            'pending':   'badge-warning',
            'paid':      'badge-info',
            'packed':    'badge-info',
            'shipped':   'badge-primary',
            'delivered': 'badge-success',
            'cancelled': 'badge-danger',
        }
        return colors.get(self.status, 'badge-secondary')

    def maps_url_buyer(self):
        """Google Maps URL for the buyer's confirmed checkout pin."""
        if self.buyer_latitude is None or self.buyer_longitude is None:
            return ''
        return (
            f'https://www.google.com/maps?q={self.buyer_latitude},'
            f'{self.buyer_longitude}'
        )


# =============================================================================
# ORDER ITEM
# =============================================================================

class OrderItem(models.Model):
    """Order line with quantity and price snapshot at sale time.

    Snapshotting protects historical totals when catalog prices change.
    """
    order              = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='items', verbose_name='Order'
    )
    product            = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        verbose_name='Product'
    )
    qty                = models.PositiveIntegerField(default=1, verbose_name='Quantity')
    unit_price_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name='Unit price (at time of sale)'
    )
    line_total         = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name        = 'Order item'
        verbose_name_plural = 'Order items'

    def save(self, *args, **kwargs):
        """Keep ``line_total`` in sync with qty × snapshot price."""
        self.line_total = self.unit_price_snapshot * self.qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.qty}x {self.product.name} en {self.order.order_number}'


# =============================================================================
# PAYMENT
# =============================================================================

class Payment(models.Model):
    """Payment record for one Order (1:1).

    Providers include mock (dev), bank transfer, and placeholders for
    Stripe/PayPal. Status drives fulfillment transitions.
    """
    PROVIDER_CHOICES = [
        ('mock', _('Mock (development)')),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('bank', _('Bank transfer')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('refunded', _('Refunded')),
    ]

    order    = models.OneToOneField(
        Order, on_delete=models.CASCADE,
        related_name='payment', verbose_name='Order'
    )
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default='mock')
    status   = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    amount   = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    paid_at  = models.DateTimeField(null=True, blank=True)
    txn_ref  = models.CharField(max_length=200, blank=True, verbose_name='Transaction reference')

    class Meta:
        verbose_name        = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f'Pago [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# SHIPMENT
# =============================================================================

class Shipment(models.Model):
    """Physical outbound shipment for a fulfilled CFZ order."""
    STATUS_CHOICES = [
        ('label', _('Label generated')),
        ('in_transit', _('In transit')),
        ('delivered', _('Delivered')),
        ('returned', _('Returned')),
    ]

    order           = models.OneToOneField(
        Order, on_delete=models.CASCADE,
        related_name='shipment', verbose_name='Order'
    )
    courier_name    = models.CharField(max_length=100, blank=True, verbose_name='Courier')
    tracking_number = models.CharField(max_length=200, blank=True, verbose_name='Tracking number')
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default='label')
    weight_kg       = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True, verbose_name='Weight (kg)',
    )
    dimensions_cm   = models.CharField(
        max_length=80, blank=True, verbose_name='Dimensions L×W×H (cm)',
    )
    warehouse_code  = models.CharField(max_length=40, blank=True, verbose_name='Bodega ZLC')
    route_code      = models.CharField(max_length=40, blank=True, verbose_name='Route')
    pickup_lat      = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    pickup_lng      = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    shipped_at      = models.DateTimeField(null=True, blank=True, verbose_name='Ship date')
    delivered_at    = models.DateTimeField(null=True, blank=True, verbose_name='Delivery date')

    class Meta:
        verbose_name        = 'Shipment'
        verbose_name_plural = 'Shipments'

    def __str__(self):
        return f'Shipment [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# DOCUMENT
# =============================================================================

class Document(models.Model):
    """Trade document attached to an order (invoice, packing list, etc.)."""
    DOC_TYPE_CHOICES = [
        ('invoice',      _('Invoice')),
        ('packing_list', _('Packing List')),
        ('other',        _('Other')),
    ]

    order      = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='documents', verbose_name='Order'
    )
    doc_type   = models.CharField(max_length=15, choices=DOC_TYPE_CHOICES, default='invoice')
    doc_number = models.CharField(max_length=100, blank=True, verbose_name='Document number')
    file_path  = models.FileField(upload_to='documents/', blank=True, null=True, verbose_name='File')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f'{self.get_doc_type_display()} {self.doc_number} — {self.order.order_number}'


# =============================================================================
# RFQ QUOTE (formal pricing before order)
# =============================================================================

class Cotizacion(models.Model):
    """Buyer RFQ asking a CFZ seller for formal unit pricing.

    Automatic quotes use catalog prices; manual ones wait for seller reply.
    ``lote`` groups broadcast RFQs; accepted quotes may link to an Order.
    """
    ESTADO_CHOICES = [
        ('pendiente', _('Pending')),
        ('respondida', _('Responded')),
        ('aceptada', _('Accepted')),
        ('rechazada', _('Rejected')),
    ]

    numero = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Number')
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cotizaciones',
        verbose_name='Buyer',
    )
    empresa = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='cotizaciones',
        verbose_name='Company',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Status',
    )
    notas_buyer = models.TextField(blank=True, verbose_name='Buyer notes')
    notas_seller = models.TextField(blank=True, verbose_name='Seller notes')
    validez_dias = models.PositiveIntegerField(default=30, verbose_name='Validity (days)')
    es_automatica = models.BooleanField(
        default=False,
        verbose_name='Automatic quote',
        help_text=_('Generated automatically with catalog pricing (no manual seller reply).'),
    )
    lote = models.CharField(
        max_length=40,
        blank=True,
        db_index=True,
        verbose_name='Broadcast batch',
        help_text=_('Groups quotes created together from one automatic request.'),
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizacion_origen',
        verbose_name='Generated order',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Quote'
        verbose_name_plural = 'Quotes'
        ordering = ['-created_at']

    @staticmethod
    def _generate_numero():
        """Build COT-YYYYMM-XXXX identifiers for new quotes."""
        now = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'COT-{now.strftime("%Y%m")}-{suffix}'

    def save(self, *args, **kwargs):
        """Mint ``numero`` on create if missing."""
        if not self.numero:
            self.numero = self._generate_numero()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero


class CotizacionItem(models.Model):
    """RFQ line with requested qty and optional seller offered price."""

    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Quote',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name='Product',
    )
    cantidad_solicitada = models.PositiveIntegerField(verbose_name='Requested quantity')
    precio_ofertado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Offered price (unit)',
    )
    notas = models.TextField(blank=True, verbose_name='Line notes')

    class Meta:
        verbose_name = 'Quote item'
        verbose_name_plural = 'Quote items'

    def __str__(self):
        return f'{self.cantidad_solicitada}× {self.product.name} ({self.cotizacion.numero})'

    @property
    def linea_total(self):
        """Line subtotal once the seller has offered a unit price."""
        if self.precio_ofertado is None:
            return None
        return self.precio_ofertado * self.cantidad_solicitada


# =============================================================================
# CARRIERS (registration + per-order assignment)
# =============================================================================

class Transportista(models.Model):
    """Registered last-mile carrier; admin must approve before activation."""

    ESTADO_CHOICES = [
        ('pendiente', _('Pending review')),
        ('aprobado', _('Approved')),
        ('rechazado', _('Rejected')),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='transportista',
        null=True,
        blank=True,
    )
    empresa_nombre = models.CharField(max_length=200)
    licencia = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    email_contacto = models.EmailField(blank=True)
    vehiculo_tipo = models.CharField(max_length=100)
    vehiculo_placa = models.CharField(max_length=30)
    cobertura_descripcion = models.TextField(
        help_text=_('Cities or areas covered'),
    )
    tarifa_base = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_aplicacion = models.DateTimeField(auto_now_add=True)
    foto_licencia = models.ImageField(upload_to='transportistas/', blank=True, null=True)
    calificacion_promedio = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('5.00'),
    )
    activo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Carrier'
        verbose_name_plural = 'Carriers'

    def __str__(self):
        nombre = self.user.get_full_name() if self.user_id else self.empresa_nombre
        return f'{self.empresa_nombre} — {nombre}'


class AsignacionTransporte(models.Model):
    """Carrier assignment for one order (buyer picks at checkout)."""

    ESTADO_CHOICES = [
        ('pendiente', _('Pending confirmation')),
        ('confirmado', _('Carrier confirmed')),
        ('en_camino', _('On the way')),
        ('entregado', _('Delivered')),
        ('cancelado', _('Cancelled')),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='asignacion_transporte',
    )
    transportista = models.ForeignKey(
        Transportista,
        on_delete=models.PROTECT,
        related_name='asignaciones',
    )
    ubicacion_pickup_lat = models.DecimalField(max_digits=10, decimal_places=7)
    ubicacion_pickup_lng = models.DecimalField(max_digits=10, decimal_places=7)
    ubicacion_pickup_descripcion = models.CharField(max_length=300, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    notas_buyer = models.TextField(blank=True)
    costo_transporte = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Transport assignment'
        verbose_name_plural = 'Transport assignments'

    def __str__(self):
        return f'{self.order.order_number} — {self.transportista.empresa_nombre}'


# =============================================================================
# EMAIL VERIFICATION (6-digit OTP — Supabase + Django fallback)
# =============================================================================

class EmailVerification(models.Model):
    """Six-digit email OTP; expires after OTP_EXPIRY_MINUTES."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verifications',
    )
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Email verification'
        verbose_name_plural = 'Email verifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_id} · {self.code} · used={self.is_used}'

    def is_valid(self) -> bool:
        """True when unused and still within the OTP TTL window."""
        from core.utils.otp_handler import OTP_EXPIRY_MINUTES

        if self.is_used:
            return False
        return timezone.now() <= self.created_at + timezone.timedelta(minutes=OTP_EXPIRY_MINUTES)

    @classmethod
    def generate_for(cls, user: User) -> 'EmailVerification':
        """Create a secure OTP via ``generate_user_otp`` and return the row."""
        from core.utils.otp_handler import generate_user_otp

        code = generate_user_otp(user)
        return cls.objects.filter(user=user, code=code, is_used=False).latest('created_at')


class PasswordResetLink(models.Model):
    """DB magic-link token for password recovery (mirrors EmailVerification).

    Plain token is emailed once; rows are deleted after successful use.
    TTL: ``PASSWORD_RESET_LINK_EXPIRY_MINUTES`` (15).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_links',
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Password reset link'
        verbose_name_plural = 'Password reset links'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_id} · reset_link · used={self.is_used}'

    def is_valid(self) -> bool:
        """True when unused and still within the reset-link TTL."""
        from core.utils.password_reset_link import PASSWORD_RESET_LINK_EXPIRY_MINUTES

        if self.is_used:
            return False
        return timezone.now() <= self.created_at + timezone.timedelta(
            minutes=PASSWORD_RESET_LINK_EXPIRY_MINUTES
        )


# Enterprise models (SaaS, ads, API, extended logistics)
from .enterprise_models import (  # noqa: E402, F401
    AdCampaign,
    AdCreditAccount,
    ApiAuditLog,
    ApiKey,
    CompanyBillingUsage,
    CompanyPlanCheckout,
    CompanyPlanCommercialRequest,
    CompanyPredictiveSnapshot,
    CompanySubscription,
    SubscriptionUpgradeLog,
    EmailDeliveryLog,
    LogisticsDispatchQueue,
    LogisticsEvent,
    LogisticsWebhookConfig,
    SaasPlan,
    generate_api_key_pair,
)
