"""ORM principal de TradeFlow Colón — marketplace B2B de la Zona Libre de Colón (ZLC).

Incluye empresas vendedoras, catálogo e inventario, pedidos de compradores,
cotizaciones RFQ, transportistas y tokens de autenticación. Las tablas
empresariales de SaaS, anuncios y API se reexportan desde ``enterprise_models``
para que ``from core.models import …`` siga siendo el punto de entrada único.
"""
from decimal import Decimal
import random
import re
import secrets   # OWASP A02: CSPRNG for OTP (random.randint is predictable)

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


# =============================================================================
# USER PROFILE
# =============================================================================

class UserProfile(models.Model):
    """Extiende el ``User`` de Django con rol y preferencias del comprador en la ZLC.

    Relación uno a uno con ``User``. El rol controla el acceso al portal
    (comprador/vendedor/admin/transportista). Las instantáneas del carrito
    alimentan recordatorios de abandono; los campos de onboarding personalizan
    el asistente posterior al registro.
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
    # GDPR: marketing consent + recorded privacy acceptance + anonymization stamp.
    marketing_opt_in = models.BooleanField(
        default=False,
        verbose_name='Marketing emails opt-in',
        help_text='User consented to cart reminders / promotional emails.',
    )
    privacy_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Privacy policy accepted at',
    )
    privacy_policy_version = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Privacy policy version accepted',
    )
    account_anonymized_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Account anonymized at',
    )
    # Staff TOTP MFA (encrypted secret) + hashed one-time backup codes.
    staff_totp_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Staff TOTP secret (encrypted)',
    )
    staff_totp_enabled = models.BooleanField(
        default=False,
        verbose_name='Staff TOTP MFA enabled',
    )
    staff_totp_backup_hashes = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Staff MFA backup code hashes',
        help_text='SHA-256 hashes of one-time backup codes (survive SECRET_KEY rotation).',
    )

    class Meta:
        """Opciones de modelo para el perfil de usuario en el admin."""
        verbose_name        = 'User profile'
        verbose_name_plural = 'User profiles'

    def __str__(self):
        """Etiqueta corta del perfil para admin y depuración."""
        return f'{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]'

    @property
    def email_verified(self) -> bool:
        """Alias en inglés; el valor persiste en ``email_verificado``."""
        return self.email_verificado

    @email_verified.setter
    def email_verified(self, value: bool) -> None:
        """Asigna el flag de verificación persistido como ``email_verificado``."""
        self.email_verificado = value


# =============================================================================
# COMPANY (CFZ SELLER)
# =============================================================================

class Company(models.Model):
    """Empresa panameña que puede comprar, vender o realizar ambas actividades.

    Los campos owner e is_verified se mantienen por compatibilidad con el portal
    existente. El flujo B2B nuevo usa membresías y verification_status para
    representar revisión documental sin afirmar una validación automática con
    entidades gubernamentales.
    """

    BUSINESS_ROLE_CHOICES = [
        ('buyer', _('Buyer')),
        ('seller', _('Seller')),
        ('both', _('Buyer and seller')),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('pending', _('Pending review')),
        ('verified', _('Verified')),
        ('rejected', _('Rejected')),
    ]

    name = models.CharField(max_length=200, verbose_name='Trade name')
    legal_name = models.CharField(max_length=200, blank=True, verbose_name='Registered legal name')
    ruc = models.CharField(max_length=50, blank=True, verbose_name='RUC / Registration')
    dv = models.CharField(max_length=20, blank=True, verbose_name='Verification digit (DV)')
    business_email = models.EmailField(blank=True, verbose_name='Business email')
    business_phone = models.CharField(max_length=30, blank=True, verbose_name='Business phone')
    address_text = models.TextField(blank=True, verbose_name='Address')
    business_role = models.CharField(
        max_length=10,
        choices=BUSINESS_ROLE_CHOICES,
        default='seller',
        verbose_name='Marketplace capability',
    )
    verification_status = models.CharField(
        max_length=12,
        choices=VERIFICATION_STATUS_CHOICES,
        default='draft',
        db_index=True,
        verbose_name='Verification status',
    )
    is_verified = models.BooleanField(default=False, verbose_name='Verified?')
    verification_document = models.FileField(
        upload_to='companies/verification/',
        blank=True,
        null=True,
        verbose_name='Verification evidence',
        help_text='Aviso de operación, registro público or equivalent evidence for manual review.',
    )
    verification_notes = models.TextField(
        blank=True,
        verbose_name='Verification notes',
        help_text='Internal notes. Do not expose these notes in the public catalog.',
    )
    verification_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Submitted for verification at',
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Verified at')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_verified',
        verbose_name='Verified by',
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_companies',
        verbose_name='Legacy owner',
        help_text='Compatibility field; new access control uses company memberships.',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CompanyMembership',
        related_name='member_companies',
        blank=True,
    )
    latitud = models.FloatField(
        null=True,
        blank=True,
        default=9.3667,
        verbose_name='Latitude (CFZ)',
    )
    longitud = models.FloatField(
        null=True,
        blank=True,
        default=-79.9000,
        verbose_name='Longitude (CFZ)',
    )
    is_featured = models.BooleanField(default=False, verbose_name='Featured on home')
    carousel_priority = models.IntegerField(default=0, verbose_name='Carousel priority')
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de identidad y consulta para empresas B2B."""
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['name']
        indexes = [
            models.Index(fields=['ruc', 'dv'], name='core_company_ruc_dv_idx'),
            models.Index(
                fields=['business_role', 'verification_status'],
                name='core_company_role_status_idx',
            ),
        ]

    def __str__(self):
        """Nombre comercial para admin, catálogo y depuración."""
        return self.name

    @staticmethod
    def normalize_identifier(value):
        """Normaliza RUC/DV sin inventar una validación gubernamental."""
        return re.sub(r'\s+', '', (value or '').strip().upper())

    @property
    def can_buy(self):
        """La empresa puede operar como compradora."""
        return self.business_role in {'buyer', 'both'}

    @property
    def can_sell(self):
        """La empresa puede operar como vendedora."""
        return self.business_role in {'seller', 'both'}

    def verification_missing_fields(self):
        """Campos mínimos exigidos antes de una revisión humana."""
        required = {
            'legal_name': _('registered legal name'),
            'ruc': _('RUC'),
            'dv': _('DV'),
            'business_email': _('business email'),
            'verification_document': _('verification evidence'),
        }
        return [
            str(label)
            for field_name, label in required.items()
            if not getattr(self, field_name)
        ]

    def clean(self):
        """Valida formato básico y bloquea verificaciones incompletas."""
        super().clean()
        self.ruc = self.normalize_identifier(self.ruc)
        self.dv = self.normalize_identifier(self.dv)

        errors = {}
        if self.ruc and not re.fullmatch(r'[A-Z0-9Ñ.\-]{3,50}', self.ruc):
            errors['ruc'] = _('Use only letters, numbers, periods and hyphens in the RUC.')
        if self.dv and not re.fullmatch(r'[A-Z0-9\-]{1,20}', self.dv):
            errors['dv'] = _('Use only letters, numbers and hyphens in the DV.')

        previous_status = None
        if self.pk:
            previous_status = (
                type(self).objects.filter(pk=self.pk)
                .values_list('verification_status', flat=True)
                .first()
            )
        if self.verification_status == 'verified' and previous_status != 'verified':
            missing = self.verification_missing_fields()
            if missing:
                errors['verification_status'] = _(
                    'Cannot verify the company. Missing: %(fields)s.'
                ) % {'fields': ', '.join(missing)}

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Mantiene RUC/DV normalizados y el flag legado sincronizado."""
        self.ruc = self.normalize_identifier(self.ruc)
        self.dv = self.normalize_identifier(self.dv)
        if self.verification_status == 'verified':
            self.is_verified = True
            if self.verified_at is None:
                self.verified_at = timezone.now()
        else:
            self.is_verified = False
            self.verified_at = None

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = list(
                set(update_fields) | {'ruc', 'dv', 'is_verified', 'verified_at'}
            )
        super().save(*args, **kwargs)

    def submit_for_verification(self):
        """Envía una identidad empresarial completa a revisión manual."""
        self.ruc = self.normalize_identifier(self.ruc)
        self.dv = self.normalize_identifier(self.dv)
        missing = self.verification_missing_fields()
        if missing:
            raise ValidationError({
                'verification_status': _(
                    'Cannot submit the company. Missing: %(fields)s.'
                ) % {'fields': ', '.join(missing)}
            })
        self.verification_status = 'pending'
        self.verification_submitted_at = timezone.now()
        self.full_clean()
        self.save(update_fields=[
            'ruc', 'dv', 'verification_status', 'verification_submitted_at',
        ])

    def mark_verified(self, reviewer):
        """Registra una decisión humana verificable y auditable."""
        self.verification_status = 'verified'
        self.verified_by = reviewer
        self.verified_at = timezone.now()
        self.full_clean()
        self.save(update_fields=[
            'verification_status', 'verified_by', 'verified_at', 'is_verified',
        ])

    def reject_verification(self, reviewer, notes=''):
        """Registra rechazo manual sin eliminar la evidencia presentada."""
        self.verification_status = 'rejected'
        self.verified_by = reviewer
        self.verification_notes = notes
        self.verified_at = None
        self.save(update_fields=[
            'verification_status', 'verified_by', 'verification_notes',
            'verified_at', 'is_verified',
        ])


class CompanyMembership(models.Model):
    """Vincula usuarios con una empresa y define su autoridad interna."""

    ROLE_CHOICES = [
        ('owner', _('Owner')),
        ('admin', _('Company administrator')),
        ('member', _('Company member')),
    ]
    STATUS_CHOICES = [
        ('invited', _('Invited')),
        ('active', _('Active')),
        ('suspended', _('Suspended')),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Una membresía por usuario y empresa."""
        verbose_name = 'Company membership'
        verbose_name_plural = 'Company memberships'
        ordering = ['company', 'role', 'user']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'user'],
                name='unique_company_user_membership',
            ),
        ]
        indexes = [
            models.Index(
                fields=['user', 'status'],
                name='core_member_user_status_idx',
            ),
        ]

    def __str__(self):
        """Etiqueta de la membresía para administración."""
        return f'{self.user} — {self.company} ({self.get_role_display()})'

    @property
    def can_manage_company(self):
        """Owners/admins activos pueden administrar la empresa."""
        return self.status == 'active' and self.role in {'owner', 'admin'}


# =============================================================================
# CATEGORY
# =============================================================================

class Category(models.Model):
    """Categoría del catálogo para navegación y filtros en la ZLC."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')

    class Meta:
        """Opciones de modelo para categorías del catálogo."""
        verbose_name        = 'Category'
        verbose_name_plural = 'Categories'
        ordering            = ['name']

    def __str__(self):
        """Nombre de la categoría para admin y depuración."""
        return self.name


# =============================================================================
# HOME PROMO SECTIONS (LIGHT CMS)
# =============================================================================

class HomePromoSection(models.Model):
    """Bloque configurable del home sin redeploy.

    Operaciones programa filas PreExpo/campañas (ofertas, destacados, banners)
    desde el admin; el merchandising resuelve productos según el tipo y los
    vínculos M2M.
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
        """Opciones de modelo para secciones promocionales del home."""
        verbose_name = _('Home promotional section')
        verbose_name_plural = _('Home promotional sections')
        ordering = ['sort_order', 'slug']

    def __str__(self):
        """Título o slug de la sección promocional."""
        return self.title_es or self.slug

    def title_for_lang(self, lang_code: str) -> str:
        """Devuelve el título ES/EN según el idioma activo de la UI."""
        if lang_code == 'en' and self.title_en:
            return self.title_en
        return self.title_es

    def subtitle_for_lang(self, lang_code: str) -> str:
        """Devuelve el subtítulo ES/EN según el idioma activo de la UI."""
        if lang_code == 'en' and self.subtitle_en:
            return self.subtitle_en
        return self.subtitle_es


# =============================================================================
# PRODUCT
# =============================================================================

class Product(models.Model):
    """SKU del catálogo ZLC perteneciente a una ``Company`` vendedora.

    Vinculado 1:1 con ``Inventory`` para el stock. Ventanas promocionales y
    prioridad de merchandising dan forma al home y a las ofertas públicas
    sin alterar el precio de lista.
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
        """Opciones de modelo para productos del catálogo."""
        verbose_name        = 'Product'
        verbose_name_plural = 'Products'
        ordering            = ['-merchandising_priority', 'name']

    def __str__(self):
        """Nombre y precio del producto para admin y depuración."""
        return f'{self.name} — {self.currency} {self.unit_price}'

    @property
    def is_on_promo_now(self) -> bool:
        """True cuando el precio promo está vigente y es menor al de lista."""
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
        """Precio unitario visible al comprador (promo si aplica; si no, lista)."""
        if self.is_on_promo_now:
            return self.promo_price
        return self.unit_price

    @property
    def discount_pct(self) -> int:
        """Ahorro en porcentaje entero frente al precio de lista mientras hay promo."""
        if not self.is_on_promo_now or self.unit_price <= 0:
            return 0
        pct = (Decimal('1') - (self.promo_price / self.unit_price)) * Decimal('100')
        return int(pct.quantize(Decimal('1')))

    @property
    def stock_qty(self):
        """Unidades en mano desde el ``Inventory`` relacionado (0 si no existe)."""
        if hasattr(self, 'inventory'):
            return self.inventory.stock_qty
        return 0

    @property
    def available_qty(self):
        """Unidades vendibles: stock menos reservado."""
        if hasattr(self, 'inventory'):
            return max(0, self.inventory.stock_qty - self.inventory.reserved_qty)
        return 0


# =============================================================================
# INVENTORY
# =============================================================================

class Inventory(models.Model):
    """Control de stock por SKU para disponibilidad en bodega ZLC.

    Uno a uno con ``Product``. Las reservas retienen unidades al crear el
    pedido; ``confirm_sale`` confirma al pagar; ``release_reservation``
    libera cancelaciones.
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
        """Opciones de modelo para inventario por SKU."""
        verbose_name        = 'Inventory'
        verbose_name_plural = 'Inventories'

    def __str__(self):
        """Resumen de stock del producto para admin y depuración."""
        return f'Inventario: {self.product.name} | Stock: {self.stock_qty}'

    @property
    def available(self):
        """Unidades libres para vender tras restar reservas."""
        return max(0, self.stock_qty - self.reserved_qty)

    @property
    def is_low_stock(self):
        """True cuando el stock disponible está en o bajo el umbral de alerta."""
        return self.available <= self.low_stock_alert

    def reserve(self, qty):
        """Retiene unidades al colocar un pedido (aún no descuenta stock)."""
        if self.available >= qty:
            self.reserved_qty += qty
            self.save(update_fields=['reserved_qty', 'updated_at'])
            return True
        return False

    def confirm_sale(self, qty):
        """Confirma unidades reservadas tras la confirmación del pago."""
        self.stock_qty   = max(0, self.stock_qty - qty)
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['stock_qty', 'reserved_qty', 'updated_at'])

    def release_reservation(self, qty):
        """Libera una reserva cuando se cancela un pedido."""
        self.reserved_qty = max(0, self.reserved_qty - qty)
        self.save(update_fields=['reserved_qty', 'updated_at'])


# =============================================================================
# ADDRESS
# =============================================================================

class Address(models.Model):
    """Dirección de envío del comprador usada en el checkout de la ZLC."""
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
        """Opciones de modelo para direcciones de envío."""
        verbose_name        = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        """Etiqueta corta de la dirección para admin y depuración."""
        return f'{self.label or "Address"} — {self.city}, {self.country}'

    def save(self, *args, **kwargs):
        """Asegura una sola dirección predeterminada por comprador."""
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# =============================================================================
# ORDER + ACCESS + CARRIERS
# =============================================================================

class TransportCarrier(models.Model):
    """Opción de transportista en checkout para logística de salida de la ZLC."""

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
        """Opciones de modelo para transportistas de checkout."""
        verbose_name = 'Transport carrier'
        verbose_name_plural = 'Transport carriers'
        ordering = ['sort_order', 'name']

    def __str__(self):
        """Nombre del transportista para admin y depuración."""
        return self.name


class UserApplication(models.Model):
    """Solicitud de acceso para onboarding comprador/vendedor (PreExpo / inversionistas)."""
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
        """Opciones de modelo para solicitudes de acceso."""
        verbose_name = 'Access request'
        verbose_name_plural = 'Access requests'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Asigna un ``review_token`` único en el primer guardado."""
        if not self.review_token:
            self.review_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        """Resumen de la solicitud de acceso para admin y depuración."""
        return f'{self.full_name} — {self.email} ({self.get_status_display()})'


class Order(models.Model):
    """Cabecera de compra del comprador en checkouts B2B y B2C de la ZLC.

    Las líneas viven en ``OrderItem``. La confirmación del vendedor condiciona
    el fulfillment cuando la empresa debe aceptar antes de empacar; los
    totales se consolidan desde las instantáneas de línea.
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
        """Opciones de modelo para pedidos."""
        verbose_name        = 'Order'
        verbose_name_plural = 'Orders'
        ordering            = ['-created_at']

    def save(self, *args, **kwargs):
        """Genera ``order_number`` al crear si aún no existe."""
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number():
        """Construye identificadores TF-YYYYMM-XXXX para pedidos nuevos."""
        now    = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'TF-{now.strftime("%Y%m")}-{suffix}'

    def __str__(self):
        """Número de pedido y comprador para admin y depuración."""
        return f'Orden {self.order_number} — {self.buyer.get_full_name() or self.buyer.username}'

    def recalculate_totals(self):
        """Recalcula subtotal y total a partir de los ``line_total`` de ``OrderItem``."""
        self.subtotal = sum(item.line_total for item in self.items.all())
        self.total    = self.subtotal + self.shipping_cost
        self.save(update_fields=['subtotal', 'total', 'updated_at'])

    def get_status_color(self):
        """Asocia el estado a la clase CSS de badge Bootstrap para paneles."""
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
        """URL de Google Maps del pin de checkout confirmado del comprador."""
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
    """Línea de pedido con cantidad e instantánea de precio al momento de la venta.

    La instantánea protege los totales históricos cuando cambian los precios
    del catálogo.
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
        """Opciones de modelo para ítems de pedido."""
        verbose_name        = 'Order item'
        verbose_name_plural = 'Order items'

    def save(self, *args, **kwargs):
        """Mantiene ``line_total`` sincronizado con cantidad × precio instantáneo."""
        self.line_total = self.unit_price_snapshot * self.qty
        super().save(*args, **kwargs)

    def __str__(self):
        """Cantidad y producto de la línea para admin y depuración."""
        return f'{self.qty}x {self.product.name} en {self.order.order_number}'


# =============================================================================
# PAYMENT
# =============================================================================

class Payment(models.Model):
    """Registro de pago para un ``Order`` (1:1).

    Proveedores: mock (desarrollo), transferencia bancaria y placeholders
    para Stripe/PayPal. El estado impulsa las transiciones de fulfillment.
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
        """Opciones de modelo para pagos de pedidos."""
        verbose_name        = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        """Estado del pago y número de pedido para admin y depuración."""
        return f'Pago [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# SHIPMENT
# =============================================================================

class Shipment(models.Model):
    """Envío físico de salida para un pedido ZLC cumplido."""
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
        """Opciones de modelo para envíos."""
        verbose_name        = 'Shipment'
        verbose_name_plural = 'Shipments'

    def __str__(self):
        """Estado del envío y número de pedido para admin y depuración."""
        return f'Shipment [{self.get_status_display()}] — {self.order.order_number}'


# =============================================================================
# DOCUMENT
# =============================================================================

class Document(models.Model):
    """Documento comercial adjunto a un pedido (factura, packing list, etc.)."""
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
        """Opciones de modelo para documentos de pedido."""
        verbose_name        = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        """Tipo y número de documento para admin y depuración."""
        return f'{self.get_doc_type_display()} {self.doc_number} — {self.order.order_number}'


# =============================================================================
# RFQ QUOTE (formal pricing before order)
# =============================================================================

class Cotizacion(models.Model):
    """RFQ del comprador pidiendo precio unitario formal a un vendedor de la ZLC.

    Las cotizaciones automáticas usan precios de catálogo; las manuales
    esperan respuesta del vendedor. ``lote`` agrupa RFQ en difusión; las
    aceptadas pueden vincularse a un ``Order``.
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
        """Opciones de modelo para cotizaciones RFQ."""
        verbose_name = 'Quote'
        verbose_name_plural = 'Quotes'
        ordering = ['-created_at']

    @staticmethod
    def _generate_numero():
        """Construye identificadores COT-YYYYMM-XXXX para cotizaciones nuevas."""
        now = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        return f'COT-{now.strftime("%Y%m")}-{suffix}'

    def save(self, *args, **kwargs):
        """Genera ``numero`` al crear si aún no existe."""
        if not self.numero:
            self.numero = self._generate_numero()
        super().save(*args, **kwargs)

    def __str__(self):
        """Número de cotización para admin y depuración."""
        return self.numero


class CotizacionItem(models.Model):
    """Línea de RFQ con cantidad solicitada y precio ofertado opcional del vendedor."""

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
        """Opciones de modelo para ítems de cotización."""
        verbose_name = 'Quote item'
        verbose_name_plural = 'Quote items'

    def __str__(self):
        """Cantidad y producto de la línea de cotización."""
        return f'{self.cantidad_solicitada}× {self.product.name} ({self.cotizacion.numero})'

    @property
    def linea_total(self):
        """Subtotal de línea una vez que el vendedor ofreció precio unitario."""
        if self.precio_ofertado is None:
            return None
        return self.precio_ofertado * self.cantidad_solicitada


# =============================================================================
# CARRIERS (registration + per-order assignment)
# =============================================================================

class Transportista(models.Model):
    """Transportista de última milla registrado; el admin debe aprobarlo antes de activarlo."""

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
        """Opciones de modelo para transportistas registrados."""
        verbose_name = 'Carrier'
        verbose_name_plural = 'Carriers'

    def __str__(self):
        """Empresa y nombre del transportista para admin y depuración."""
        nombre = self.user.get_full_name() if self.user_id else self.empresa_nombre
        return f'{self.empresa_nombre} — {nombre}'


class AsignacionTransporte(models.Model):
    """Asignación de transportista a un pedido (el comprador elige en checkout)."""

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
        """Opciones de modelo para asignaciones de transporte."""
        verbose_name = 'Transport assignment'
        verbose_name_plural = 'Transport assignments'

    def __str__(self):
        """Pedido y transportista asignado para admin y depuración."""
        return f'{self.order.order_number} — {self.transportista.empresa_nombre}'


# =============================================================================
# EMAIL VERIFICATION (6-digit OTP — Supabase + Django fallback)
# =============================================================================

class EmailVerification(models.Model):
    """OTP de correo de seis dígitos; en BD se guarda el hash SHA-256."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verifications',
    )
    # SHA-256 hex digest of the 6-digit OTP (never store plaintext).
    code = models.CharField(max_length=64, db_index=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para verificaciones OTP por correo."""
        verbose_name = 'Email verification'
        verbose_name_plural = 'Email verifications'
        ordering = ['-created_at']

    def __str__(self):
        """Resumen del OTP de correo para admin y depuración."""
        return f'{self.user_id} · otp_hash · used={self.is_used}'

    def is_valid(self) -> bool:
        """True si no se ha usado y sigue dentro de la ventana TTL del OTP."""
        from core.utils.otp_handler import OTP_EXPIRY_MINUTES

        if self.is_used:
            return False
        return timezone.now() <= self.created_at + timezone.timedelta(minutes=OTP_EXPIRY_MINUTES)

    @classmethod
    def generate_for(cls, user: User) -> 'EmailVerification':
        """Crea un OTP hasheado y adjunta ``plain_code`` efímero para el email."""
        from core.utils.otp_handler import generate_user_otp
        from core.utils.secret_hash import hash_secret

        plain = generate_user_otp(user)
        row = cls.objects.filter(
            user=user, code=hash_secret(plain), is_used=False,
        ).latest('created_at')
        # Never persisted — only for the one-time email send path.
        row.plain_code = plain
        return row


class PasswordResetLink(models.Model):
    """Token magic-link hasheado en BD para recuperación de contraseña.

    El token en claro se envía una sola vez por correo; en BD solo vive el
    digest SHA-256. Las filas se eliminan tras un uso exitoso.
    TTL: ``PASSWORD_RESET_LINK_EXPIRY_MINUTES`` (15).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_links',
    )
    # SHA-256 hex digest of the opaque URL token.
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para enlaces de restablecimiento de contraseña."""
        verbose_name = 'Password reset link'
        verbose_name_plural = 'Password reset links'
        ordering = ['-created_at']

    def __str__(self):
        """Resumen del enlace de restablecimiento para admin y depuración."""
        return f'{self.user_id} · reset_link_hash · used={self.is_used}'

    def is_valid(self) -> bool:
        """True si no se ha usado y sigue dentro del TTL del enlace de reset."""
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
