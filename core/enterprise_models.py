"""
Modelos enterprise: planes SaaS, ads, logística API y API keys.
Extienden la arquitectura existente sin reemplazar modelos core.
"""
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SaasPlan(models.Model):
    """Plan comercial TradeFlow (Digitalízate → Enterprise)."""

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    monthly_volume_limit_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Null = volumen ilimitado'),
    )
    ad_credits_monthly = models.PositiveIntegerField(default=0)
    api_access = models.BooleanField(default=False)
    logistics_webhooks = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    predictive_ai = models.BooleanField(
        default=False,
        verbose_name=_('IA predictiva Enterprise'),
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'slug']
        verbose_name = 'Plan SaaS'
        verbose_name_plural = 'Planes SaaS'

    def __str__(self):
        return self.name

    @property
    def is_unlimited(self) -> bool:
        return self.monthly_volume_limit_usd is None


class CompanySubscription(models.Model):
    """Suscripción activa de una empresa vendedora."""

    STATUS_CHOICES = [
        ('trialing', _('Prueba')),
        ('active', _('Activa')),
        ('past_due', _('Pago pendiente')),
        ('cancelled', _('Cancelada')),
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Suscripción empresa'
        verbose_name_plural = 'Suscripciones empresa'

    def __str__(self):
        return f'{self.company.name} — {self.plan.name}'


class CompanyBillingUsage(models.Model):
    """Volumen facturable agregado por empresa y mes."""

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
        verbose_name = 'Uso facturación mensual'
        verbose_name_plural = 'Uso facturación mensual'

    def __str__(self):
        return f'{self.company_id} {self.period_year}-{self.period_month:02d}'


class CompanyPredictiveSnapshot(models.Model):
    """Caché de insights predictivos (Enterprise) por empresa y período."""

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
        verbose_name = 'Snapshot predictivo'
        verbose_name_plural = 'Snapshots predictivos'
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
        verbose_name = 'Cuenta créditos ads'
        verbose_name_plural = 'Cuentas créditos ads'


class AdCampaign(models.Model):
    PLACEMENT_CHOICES = [
        ('search', _('Búsqueda')),
        ('home', _('Home')),
        ('category', _('Categoría')),
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
        verbose_name = 'Campaña publicitaria'
        verbose_name_plural = 'Campañas publicitarias'

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
    name = models.CharField(max_length=120, default='Aliado logístico')
    endpoint_url = models.URLField(max_length=500)
    signing_secret = models.CharField(max_length=128)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Webhook logístico'
        verbose_name_plural = 'Webhooks logísticos'


class LogisticsEvent(models.Model):
    """Eventos de timeline / auditoría logística."""

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
        verbose_name = 'Evento logístico'
        verbose_name_plural = 'Eventos logísticos'


class LogisticsDispatchQueue(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pendiente')),
        ('sent', _('Enviado')),
        ('failed', _('Fallido')),
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
        verbose_name = 'Cola despacho logístico'
        verbose_name_plural = 'Cola despacho logístico'


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
        help_text=_('inventory.read, pricing.write, webhooks.receive'),
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
        verbose_name = 'Auditoría API'
        verbose_name_plural = 'Auditoría API'


class EmailDeliveryLog(models.Model):
    """Auditoría de correos transaccionales (entregabilidad / diagnóstico)."""

    STATUS_CHOICES = [
        ('sent', _('Enviado')),
        ('failed', _('Fallido')),
        ('queued', _('En cola')),
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
        verbose_name = 'Log de correo'
        verbose_name_plural = 'Logs de correo'


def generate_api_key_pair() -> tuple[str, str, str]:
    """Devuelve (raw_key, prefix, sha256_hash)."""
    import hashlib

    raw = f'tf_live_{secrets.token_urlsafe(32)}'
    prefix = raw[:12]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, digest
