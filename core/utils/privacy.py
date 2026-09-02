"""GDPR helpers: subject data export and account anonymization."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_tz

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

log = logging.getLogger('tradeflow.security')

PRIVACY_POLICY_VERSION = '2026-07'


def build_user_export(user: User) -> dict:
    """Assemble a portable JSON-serializable dump of the subject's data."""
    profile = getattr(user, 'profile', None)
    addresses = []
    if hasattr(user, 'addresses'):
        for a in user.addresses.all():
            addresses.append({
                'label': a.label,
                'country': a.country,
                'city': a.city,
                'line1': a.line1,
                'line2': a.line2,
                'postal_code': a.postal_code,
                'is_default': a.is_default,
            })
    orders = []
    if hasattr(user, 'orders'):
        for o in user.orders.all().order_by('-created_at')[:500]:
            orders.append({
                'order_number': o.order_number,
                'status': o.status,
                'total': str(o.total),
                'created_at': o.created_at.isoformat() if o.created_at else None,
            })
    apps = []
    from core.models import UserApplication
    for app in UserApplication.objects.filter(user=user).order_by('-created_at')[:50]:
        apps.append({
            'status': app.status,
            'role': app.role,
            'created_at': app.created_at.isoformat() if getattr(app, 'created_at', None) else None,
        })

    return {
        'exported_at': datetime.now(tz=dt_tz.utc).isoformat(),
        'privacy_policy_version': PRIVACY_POLICY_VERSION,
        'user': {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        },
        'profile': {
            'phone': getattr(profile, 'phone', '') if profile else '',
            'role': getattr(profile, 'role', '') if profile else '',
            'email_verified': bool(getattr(profile, 'email_verificado', False)) if profile else False,
            'marketing_opt_in': bool(getattr(profile, 'marketing_opt_in', False)) if profile else False,
            'privacy_accepted_at': (
                profile.privacy_accepted_at.isoformat()
                if profile and profile.privacy_accepted_at else None
            ),
            'business_role_intent': getattr(profile, 'business_role_intent', '') if profile else '',
        },
        'addresses': addresses,
        'orders': orders,
        'applications': apps,
    }


def export_user_json_bytes(user: User) -> bytes:
    """Serialize ``build_user_export`` as UTF-8 JSON bytes."""
    return json.dumps(build_user_export(user), ensure_ascii=False, indent=2).encode('utf-8')


@transaction.atomic
def anonymize_user(user: User) -> None:
    """Irreversibly anonymize a subject while preserving order integrity.

    Orders keep ``PROTECT`` FKs: the User row stays but PII is scrubbed and
    the account is deactivated. Related OTP/reset rows are deleted.
    """
    from core.models import EmailVerification, PasswordResetLink, UserProfile

    uid = user.pk
    anon_name = f'deleted_user_{uid}'
    anon_email = f'deleted_{uid}@anonymized.invalid'

    EmailVerification.objects.filter(user=user).delete()
    PasswordResetLink.objects.filter(user=user).delete()

    user.username = anon_name[:150]
    user.email = anon_email
    user.first_name = ''
    user.last_name = ''
    user.is_active = False
    user.set_unusable_password()
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'buyer'})
    profile.phone = ''
    profile.token_verificacion = None
    profile.codigo_verificacion_email = ''
    profile.codigo_verificacion_expira = None
    profile.email_verificado = False
    profile.marketing_opt_in = False
    profile.cart_items_count = 0
    profile.cart_last_activity_at = None
    profile.cart_reminder_sent_at = None
    profile.business_role_intent = ''
    profile.account_anonymized_at = timezone.now()
    profile.save()

    # Scrub shipping PII on orders / addresses owned by this user.
    if hasattr(user, 'addresses'):
        user.addresses.all().delete()
    if hasattr(user, 'orders'):
        user.orders.update(
            buyer_latitude=None,
            buyer_longitude=None,
            notes='',
        )

    log.info('gdpr_account_anonymized user_id=%s', uid)
