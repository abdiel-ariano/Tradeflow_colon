"""Modelos empresariales de SaaS, anuncios, API logística y auditoría para vendedores ZLC.

Extienden las tablas de catálogo/pedidos del núcleo sin reemplazarlas. Los
planes limitan volúmenes, créditos publicitarios, webhooks e IA predictiva
para comerciantes de la Zona Libre de Colón.
"""
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SaasPlan(models.Model):
    """Nivel comercial de plan TradeFlow (Digitalize → Enterprise).

    Los topes de volumen y los flags de funcionalidad definen qué puede usar
    cada vendedor de la ZLC.
    """

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    monthly_volume_limit_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Null = unlimited volume',
    )
    ad_credits_monthly = models.PositiveIntegerField(default=0)
    api_access = models.BooleanField(default=False)
    logistics_webhooks = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    predictive_ai = models.BooleanField(
        default=False,
        verbose_name='Enterprise predictive AI',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        """Opciones de modelo para planes SaaS."""
        ordering = ['sort_order', 'slug']
        verbose_name = 'SaaS plan'
        verbose_name_plural = 'SaaS plans'

    def __str__(self):
        """Nombre del plan SaaS para admin y depuración."""
        return self.name

    @property
    def is_unlimited(self) -> bool:
        """True cuando el GMV mensual no tiene tope."""
        return self.monthly_volume_limit_usd is None


class CompanySubscription(models.Model):
    """Ciclo de vida de la suscripción SaaS de una empresa vendedora de la ZLC.

    Ciclo (ver ``core/utils/seller_lifecycle.py``):
    - ``trialing``: Digitalize gratis 30 días tras el asistente de empresa.
    - ``active``: plan de pago (upgrade en trial o tras la gracia).
    - ``past_due``: trial terminado; 7 días de gracia para activar ≥ recomendado.
    - ``cancelled``: baja suave; portal bloqueado, SKUs salen del marketplace.
    """

    STATUS_CHOICES = [
        ('trialing', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Payment past due'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.OneToOneField(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    upgraded_at = models.DateTimeField(null=True, blank=True)
    # Snapshot at day 30: billable USD volume during the trial.
    trial_volume_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='USD vendidos durante el trial; fijado al finalizar el periodo.',
    )
    # Minimum plan allowed at post-trial checkout (no downgrade).
    recommended_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_for_subscriptions',
        help_text='Plan mínimo tras el trial según volumen; bloquea planes inferiores.',
    )
    # End of past_due grace; after this date → soft cancellation.
    grace_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Último día para activar plan antes de cancelación automática.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para suscripciones de empresa."""
        verbose_name = 'Company subscription'
        verbose_name_plural = 'Company subscriptions'

    def __str__(self):
        """Empresa y plan de la suscripción para admin y depuración."""
        return f'{self.company.name} — {self.plan.name}'


class CompanyBillingUsage(models.Model):
    """GMV facturable agregado por empresa y mes calendario."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='billing_usage',
    )
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()
    volume_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    orders_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Opciones de modelo para uso de facturación mensual."""
        unique_together = [('company', 'period_year', 'period_month')]
        verbose_name = 'Monthly billing usage'
        verbose_name_plural = 'Monthly billing usage'

    def __str__(self):
        """Empresa y periodo de uso de facturación."""
        return f'{self.company_id} {self.period_year}-{self.period_month:02d}'


class SubscriptionUpgradeLog(models.Model):
    """Historial persistente de cambios de plan (Supabase / PostgreSQL)."""

    SOURCE_CHOICES = [
        ('self_serve', 'Seller activation'),
        ('checkout', 'Checkout payment'),
        ('commercial', 'Commercial approval'),
        ('admin', 'Administrator'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='subscription_upgrades',
    )
    from_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upgrades_from',
    )
    to_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.PROTECT,
        related_name='upgrades_to',
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='self_serve')
    activated_at = models.DateTimeField(default=timezone.now)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        """Opciones de modelo para el historial de upgrades de plan."""
        ordering = ['-activated_at']
        verbose_name = 'Plan upgrade history'
        verbose_name_plural = 'Plan upgrade history'


class CompanyPlanCheckout(models.Model):
    """Sesión de pago de plan SaaS (demo mock o transferencia bancaria, sin Stripe).

    Flujo bancario (producción):
    1. El vendedor elige plan → checkout ``pending`` + ``provider=bank``.
    2. Envía referencia/comprobante → permanece ``pending`` hasta revisión.
    3. El admin aprueba → ``complete_plan_checkout`` → suscripción ``active``.
    """

    STATUS_CHOICES = [
        ('pending', 'Payment pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected'),
    ]
    PROVIDER_CHOICES = [
        ('mock', 'Card (demo)'),
        ('stripe', 'Stripe (disabled)'),
        ('bank', 'Bank transfer'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='plan_checkouts',
    )
    from_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkouts_from',
    )
    target_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.PROTECT,
        related_name='checkouts_to',
    )
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    billing_label = models.CharField(max_length=40, default='Monthly')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=12, choices=PROVIDER_CHOICES, default='bank')
    txn_ref = models.CharField(max_length=120, blank=True)
    # Reference the seller quotes when transferring (bank operation number).
    transfer_reference = models.CharField(
        max_length=120,
        blank=True,
        help_text='Referencia / número de operación bancaria indicado por el seller.',
    )
    seller_notes = models.CharField(max_length=255, blank=True)
    proof_file = models.FileField(
        upload_to='plan_receipts/',
        blank=True,
        null=True,
        help_text='Comprobante de transferencia (PDF/imagen).',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_plan_checkouts',
    )
    review_notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Opciones de modelo para checkouts de plan SaaS."""
        ordering = ['-created_at']
        verbose_name = 'SaaS plan checkout'
        verbose_name_plural = 'SaaS plan checkouts'

    def __str__(self):
        """Empresa, plan destino y estado del checkout."""
        return f'{self.company.name} → {self.target_plan.slug} [{self.status}]'


class CompanyPlanCommercialRequest(models.Model):
    """Solicitud comercial Enterprise vinculada a una empresa (respaldada en Supabase)."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('en_revision', 'Under review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='plan_commercial_requests',
    )
    requested_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.PROTECT,
        related_name='commercial_requests',
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    company_legal_name = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    user_application = models.ForeignKey(
        'core.UserApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_commercial_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Opciones de modelo para solicitudes comerciales de plan."""
        ordering = ['-created_at']
        verbose_name = 'Commercial plan request'
        verbose_name_plural = 'Commercial plan requests'


class CompanyPredictiveSnapshot(models.Model):
    """Instantánea cacheada de insights predictivos (Enterprise) por empresa y periodo."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='predictive_snapshots',
    )
    period_key = models.CharField(max_length=20, db_index=True)
    payload = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Opciones de modelo para instantáneas predictivas."""
        unique_together = [('company', 'period_key')]
        verbose_name = 'Predictive snapshot'
        verbose_name_plural = 'Predictive snapshots'
        ordering = ['-computed_at']


class AdCreditAccount(models.Model):
    """Saldo de créditos publicitarios del vendedor para campañas de impulso en el marketplace."""

    company = models.OneToOneField(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='ad_credits',
    )
    balance = models.PositiveIntegerField(default=0)
    lifetime_spent = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Opciones de modelo para cuentas de créditos publicitarios."""
        verbose_name = 'Ad credits account'
        verbose_name_plural = 'Ad credits accounts'


class AdCampaign(models.Model):
    """Colocación de pago que impulsa un SKU del vendedor en búsqueda/home/categoría."""

    PLACEMENT_CHOICES = [
        ('search', 'Search'),
        ('home', 'Home'),
        ('category', 'Category'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
    )
    product = models.ForeignKey(
        'core.Product',
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES, default='search')
    boost_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.50'))
    credits_budget = models.PositiveIntegerField(default=0)
    credits_spent = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para campañas publicitarias."""
        verbose_name = 'Ad campaign'
        verbose_name_plural = 'Ad campaigns'

    def __str__(self):
        """Nombre de la campaña publicitaria para admin y depuración."""
        return self.name


class LogisticsWebhookConfig(models.Model):
    """Endpoint de webhook del socio para eventos logísticos salientes firmados."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='logistics_webhooks',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120, default='Logistics partner')
    endpoint_url = models.URLField(max_length=500)
    signing_secret = models.CharField(max_length=128)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para webhooks de logística."""
        verbose_name = 'Logistics webhook'
        verbose_name_plural = 'Logistics webhooks'

    def clean(self):
        """Reject private/metadata SSRF targets before the webhook is saved."""
        from django.core.exceptions import ValidationError

        from core.utils.url_validator import validate_outbound_url

        try:
            validate_outbound_url(self.endpoint_url)
        except ValueError as exc:
            raise ValidationError({'endpoint_url': str(exc)}) from exc

    def save(self, *args, **kwargs):
        """Run full_clean so admin/API saves cannot skip SSRF checks."""
        self.full_clean()
        return super().save(*args, **kwargs)


class LogisticsEvent(models.Model):
    """Evento de línea de tiempo / auditoría del recorrido logístico de un pedido."""

    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        related_name='logistics_events',
    )
    event_type = models.CharField(max_length=40)
    label = models.CharField(max_length=200, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=20, default='system')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para eventos logísticos."""
        ordering = ['created_at']
        verbose_name = 'Logistics event'
        verbose_name_plural = 'Logistics events'


class LogisticsDispatchQueue(models.Model):
    """Cola de entrega de webhooks salientes con metadatos de reintento."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        related_name='logistics_dispatches',
    )
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='logistics_dispatches',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=128, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Opciones de modelo para la cola de despacho logístico."""
        verbose_name = 'Logistics dispatch queue'
        verbose_name_plural = 'Logistics dispatch queue'


class ApiKey(models.Model):
    """Clave API del vendedor hasheada para integraciones de inventario/precios/webhooks."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='api_keys',
    )
    name = models.CharField(max_length=80)
    key_prefix = models.CharField(max_length=12, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    scopes = models.JSONField(
        default=list,
        help_text='inventory.read, pricing.write, webhooks.receive',
    )
    is_active = models.BooleanField(default=True)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_api_keys',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Opciones de modelo para claves API."""
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'

    def __str__(self):
        """Nombre y prefijo de la clave API para admin y depuración."""
        return f'{self.name} ({self.key_prefix}…)'


class ApiAuditLog(models.Model):
    """Auditoría de solicitudes por uso de clave API del vendedor."""

    api_key = models.ForeignKey(
        ApiKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='api_audit_logs',
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField(default=200)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para logs de auditoría de API."""
        ordering = ['-created_at']
        verbose_name = 'API audit log'
        verbose_name_plural = 'API audit logs'


class EmailDeliveryLog(models.Model):
    """Auditoría de correo transaccional para diagnóstico de entregabilidad."""

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('queued', 'Queued'),
    ]

    email_type = models.CharField(max_length=40, db_index=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='queued')
    error_message = models.TextField(blank=True)
    backend = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Opciones de modelo para logs de entrega de correo."""
        ordering = ['-created_at']
        verbose_name = 'Email log'
        verbose_name_plural = 'Email logs'


def generate_api_key_pair() -> tuple[str, str, str]:
    """Crea el triple de clave API en vivo: secreto, prefijo y hash SHA-256."""
    import hashlib

    raw = f'tf_live_{secrets.token_urlsafe(32)}'
    prefix = raw[:12]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, digest
