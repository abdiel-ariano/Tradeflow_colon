"""
Password reset form that delivers mail via Resend (same path as OTP / transactional).

Django's stock PasswordResetForm uses django.core.mail → EMAIL_BACKEND
(console by default), which never reaches production inboxes.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.template import loader

from core.utils.email_delivery import deliver_mail

log = logging.getLogger('tradeflow.email')


def password_reset_domain_and_https(request=None) -> tuple[str | None, bool]:
    """
    Prefer PUBLIC_BASE_URL so reset links use the public host (not Site.domain /
    example.com). Falls back to request host / Site via domain_override=None.
    """
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    use_https = bool(request and request.is_secure())
    if not base:
        return None, use_https

    parsed = urlparse(base if '://' in base else f'https://{base}')
    domain = parsed.netloc or None
    if parsed.scheme == 'https':
        use_https = True
    elif parsed.scheme == 'http':
        use_https = False
    return domain, use_https


def password_reset_extra_context() -> dict:
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    return {'public_base_url': base}


class ResendPasswordResetForm(PasswordResetForm):
    """Generate the usual Django reset token; send the email through Resend."""

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)
        html_email = None
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)

        sender = (from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()
        try:
            # fail_silently=True: always show the same "check your email" page
            # (no account enumeration via 500s). Failures go to EmailDeliveryLog.
            ok = deliver_mail(
                subject=subject,
                message=body,
                from_email=sender,
                recipient_list=[to_email],
                html_message=html_email,
                email_type='password_reset',
                fail_silently=True,
            )
            if not ok:
                log.error(
                    'password_reset_email_not_sent to=%s (see EmailDeliveryLog)',
                    to_email,
                )
        except Exception:
            # Mirror Django 6 PasswordResetForm: log, do not raise to the user.
            log.exception('Failed to send password reset email to %s', to_email)
