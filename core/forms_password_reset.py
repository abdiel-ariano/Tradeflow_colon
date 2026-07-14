"""
Password reset form that delivers mail via Resend (same path as OTP / transactional).

Tokens come from ``PasswordResetLink`` (DB, mirrors EmailVerification), not Django's
HMAC PasswordResetTokenGenerator.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.sites.shortcuts import get_current_site
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.utils.email_delivery import deliver_mail
from core.utils.password_reset_link import generate_password_reset_link

log = logging.getLogger('tradeflow.email')
UserModel = get_user_model()


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
    """Persist a DB magic-link token and send it through Resend."""

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
            log.exception('Failed to send password reset email to %s', to_email)

    def save(
        self,
        domain_override=None,
        subject_template_name='registration/password_reset_subject.txt',
        email_template_name='registration/password_reset_email.html',
        use_https=False,
        token_generator=None,  # ignored — DB tokens via generate_password_reset_link
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        """
        Same contract as Django PasswordResetForm.save, but tokens are PasswordResetLink rows.
        Does not call User.set_password / make_password.
        """
        email = self.cleaned_data['email']
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override

        email_field_name = UserModel.get_email_field_name()
        for user in self.get_users(email):
            user_email = getattr(user, email_field_name)
            token = generate_password_reset_link(user)
            user_pk_bytes = force_bytes(UserModel._meta.pk.value_to_string(user))
            context = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(user_pk_bytes),
                'user': user,
                'token': token,
                'protocol': 'https' if use_https else 'http',
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user_email,
                html_email_template_name=html_email_template_name,
            )
