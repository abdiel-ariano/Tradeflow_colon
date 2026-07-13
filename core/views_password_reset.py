"""Auth views specific to password recovery (Resend delivery + public domain links)."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from core.forms_password_reset import (
    ResendPasswordResetForm,
    password_reset_domain_and_https,
    password_reset_extra_context,
)


class TradeFlowPasswordResetView(auth_views.PasswordResetView):
    """
    Stock Django reset flow, but:
    - emails go through Resend (ResendPasswordResetForm)
    - reset links use PUBLIC_BASE_URL host/scheme when configured
    """

    form_class = ResendPasswordResetForm
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    html_email_template_name = 'registration/password_reset_email_html.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    from_email = None  # resolved in form_valid from DEFAULT_FROM_EMAIL

    def form_valid(self, form):
        domain, use_https = password_reset_domain_and_https(self.request)
        opts = {
            'use_https': use_https,
            'token_generator': self.token_generator,
            'from_email': self.from_email or settings.DEFAULT_FROM_EMAIL,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': {
                **password_reset_extra_context(),
                **(self.extra_email_context or {}),
            },
        }
        if domain:
            opts['domain_override'] = domain
        form.save(**opts)
        # Skip PasswordResetView.form_valid (would call form.save again).
        return FormView.form_valid(self, form)


class TradeFlowPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
