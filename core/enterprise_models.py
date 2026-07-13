"""
Enterprise models: SaaS plans, ads, logistics API, and API keys.
Extends the existing architecture without replacing core models.
"""
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SaasPlan(models.Model):
    """Commercial TradeFlow plan (Digitalize → Enterprise)."""

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
        ordering = ['sort_order', 'slug']
        verbose_name = 'SaaS plan'
        verbose_name_plural = 'SaaS plans'

    def __str__(self):
        return self.name

    @property
    def is_unlimited(self) -> bool:
        """Is unlimited."""
        return self.monthly_volume_limit_usd is None


class CompanySubscription(models.Model):
    """
    Suscripción SaaS de una empresa vendedora.

    Ciclo de vida (ver ``core/utils/seller_lifecycle.py``):
    - ``trialing``: 30 días gratis en Digitalízate tras wizard de empresa.
    - ``active``: plan pagado (upgrade durante trial o activación post-gracia).
    - ``past_due``: trial vencido; 7 días de gracia para activar plan ≥ recomendado.
    - ``cancelled``: baja media; portal bloqueado y productos fuera del marketplace.
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
    # Snapshot al día 30: volumen USD facturable durante el trial.
    trial_volume_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='USD vendidos durante el trial; fijado al finalizar el periodo.',
    )
    # Plan mínimo permitido en checkout post-trial (no downgrade).
    recommended_plan = models.ForeignKey(
        SaasPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_for_subscriptions',
        help_text='Plan mínimo tras el trial según volumen; bloquea planes inferiores.',
    )
    # Fin de la ventana de gracia (past_due); tras esta fecha → baja media.
    grace_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Último día para activar plan antes de cancelación automática.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Company subscription'
        verbose_name_plural = 'Company subscriptions'

    def __str__(self):
        return f'{self.company.name} — {self.plan.name}'


class CompanyBillingUsage(models.Model):
    """Billable volume aggregated by company and month."""

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
        unique_together = [('company', 'period_year', 'period_month')]
        verbose_name = 'Monthly billing usage'
        verbose_name_plural = 'Monthly billing usage'

    def __str__(self):
        return f'{self.company_id} {self.period_year}-{self.period_month:02d}'


class SubscriptionUpgradeLog(models.Model):
    """Persistent plan change history (Supabase / PostgreSQL)."""

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
        ordering = ['-activated_at']
        verbose_name = 'Plan upgrade history'
        verbose_name_plural = 'Plan upgrade history'


class CompanyPlanCheckout(models.Model):
    """SaaS subscription checkout (simulated payment or future provider)."""

    STATUS_CHOICES = [
        ('pending', 'Payment pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    PROVIDER_CHOICES = [
        ('mock', 'Card (demo)'),
        ('stripe', 'Stripe'),
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
    provider = models.CharField(max_length=12, choices=PROVIDER_CHOICES, default='mock')
    txn_ref = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SaaS plan checkout'
        verbose_name_plural = 'SaaS plan checkouts'

    def __str__(self):
        return f'{self.company.name} → {self.target_plan.slug} [{self.status}]'


class CompanyPlanCommercialRequest(models.Model):
    """Enterprise commercial request linked to a company (persistent in Supabase)."""

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
        ordering = ['-created_at']
        verbose_name = 'Commercial plan request'
        verbose_name_plural = 'Commercial plan requests'


class CompanyPredictiveSnapshot(models.Model):
    """Predictive insights cache (Enterprise) by company and period."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='predictive_snapshots',
    )
    period_key = models.CharField(max_length=20, db_index=True)
    payload = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'period_key')]
        verbose_name = 'Predictive snapshot'
        verbose_name_plural = 'Predictive snapshots'
        ordering = ['-computed_at']


class AdCreditAccount(models.Model):
    company = models.OneToOneField(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='ad_credits',
    )
    balance = models.PositiveIntegerField(default=0)
    lifetime_spent = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ad credits account'
        verbose_name_plural = 'Ad credits accounts'


class AdCampaign(models.Model):
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
        verbose_name = 'Ad campaign'
        verbose_name_plural = 'Ad campaigns'

    def __str__(self):
        return self.name


class LogisticsWebhookConfig(models.Model):
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
        verbose_name = 'Logistics webhook'
        verbose_name_plural = 'Logistics webhooks'


class LogisticsEvent(models.Model):
    """Timeline / logistics audit events."""

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
        ordering = ['created_at']
        verbose_name = 'Logistics event'
        verbose_name_plural = 'Logistics events'


class LogisticsDispatchQueue(models.Model):
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
        verbose_name = 'Logistics dispatch queue'
        verbose_name_plural = 'Logistics dispatch queue'


class ApiKey(models.Model):
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
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'

    def __str__(self):
        return f'{self.name} ({self.key_prefix}…)'


class ApiAuditLog(models.Model):
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
        ordering = ['-created_at']
        verbose_name = 'API audit log'
        verbose_name_plural = 'API audit logs'


class EmailDeliveryLog(models.Model):
    """Transactional email audit (deliverability / diagnostics)."""

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
        ordering = ['-created_at']
        verbose_name = 'Email log'
        verbose_name_plural = 'Email logs'


def generate_api_key_pair() -> tuple[str, str, str]:
    """Returns (raw_key, prefix, sha256_hash)."""
    import hashlib

    raw = f'tf_live_{secrets.token_urlsafe(32)}'
    prefix = raw[:12]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, digest
