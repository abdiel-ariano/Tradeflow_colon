"""Password recovery via Resend email and DB-backed magic links.

Uses ``PasswordResetLink`` rows instead of Django's default token
generator so links can be audited, expired, and consumed once for
marketplace accounts (buyers, sellers, and admins).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    PasswordContextMixin,
    PasswordResetView,
)
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic.edit import FormView

try:
    from django.contrib.auth.decorators import login_not_required
except ImportError:  # pragma: no cover
    def login_not_required(view):
        """No-op shim when Django lacks ``login_not_required``."""
        return view

from core.forms_password_reset import (
    ResendPasswordResetForm,
    password_reset_domain_and_https,
    password_reset_extra_context,
)
from core.utils.password_reset_link import (
    consume_password_reset_link,
    lookup_password_reset_link,
)

log = logging.getLogger('tradeflow.email')
UserModel = get_user_model()


class TradeFlowPasswordResetView(PasswordResetView):
    """Collect email, create a magic link, and send it via Resend."""

    form_class = ResendPasswordResetForm
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    html_email_template_name = 'registration/password_reset_email_html.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    from_email = None

    def form_valid(self, form):
        """Persist the reset link and dispatch the Resend email."""
        domain, use_https = password_reset_domain_and_https(self.request)
        opts = {
            'use_https': use_https,
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
        return FormView.form_valid(self, form)


@method_decorator([login_not_required, csrf_protect], name='dispatch')
@method_decorator(sensitive_post_parameters(), name='dispatch')
@method_decorator(never_cache, name='dispatch')
class TradeFlowPasswordResetConfirmView(PasswordContextMixin, FormView):
    """Validate a DB magic link, then set a new password.

    Password hashing goes only through Django ``SetPasswordForm.save()``
    (``user.set_password``). Invalid or consumed links render the
    unsuccessful state without building the form.
    """

    form_class = SetPasswordForm
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    post_reset_login = True
    post_reset_login_backend = 'django.contrib.auth.backends.ModelBackend'
    reset_url_token = 'set-password'
    title = 'Enter new password'

    def dispatch(self, *args, **kwargs):
        """Resolve uid/token, stash session token, or show invalid link."""
        if 'uidb64' not in kwargs or 'token' not in kwargs:
            raise ImproperlyConfigured(
                "URL must contain 'uidb64' and 'token' parameters."
            )

        self.validlink = False
        self.user = self.get_user(kwargs['uidb64'])
        token = kwargs['token']

        if self.user is not None:
            if token == self.reset_url_token:
                session_token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
                result = lookup_password_reset_link(
                    user=self.user, raw_token=session_token or ''
                )
                if result.ok:
                    self.validlink = True
                    return super().dispatch(*args, **kwargs)
            else:
                result = lookup_password_reset_link(user=self.user, raw_token=token)
                if result.ok:
                    self.request.session[INTERNAL_RESET_SESSION_TOKEN] = token
                    redirect_url = self.request.path.replace(token, self.reset_url_token)
                    return HttpResponseRedirect(redirect_url)

        return self.render_to_response(self.get_context_data())

    def get_user(self, uidb64):
        """Decode uidb64 to a User, or None if the id is invalid."""
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            pk = UserModel._meta.pk.to_python(uid)
            user = UserModel._default_manager.get(pk=pk)
        except (
            TypeError,
            ValueError,
            OverflowError,
            UserModel.DoesNotExist,
            ValidationError,
        ):
            user = None
        return user

    def get_form_kwargs(self):
        """Pass the resolved user into ``SetPasswordForm``."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.user
        return kwargs

    def form_valid(self, form):
        """Consume the magic link, save password, and optionally log in."""
        session_token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
        consumed = consume_password_reset_link(
            user=self.user, raw_token=session_token or ''
        )
        if not consumed.ok:
            self.validlink = False
            log.warning(
                'password_reset_confirm_rejected reason=consume_failed user_id=%s',
                getattr(self.user, 'pk', None),
            )
            return self.render_to_response(self.get_context_data())

        # Django SetPasswordForm.save() → user.set_password(...).
        user = form.save()
        del self.request.session[INTERNAL_RESET_SESSION_TOKEN]
        if self.post_reset_login:
            auth_login(self.request, user, self.post_reset_login_backend)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Expose ``validlink`` and suppress the form on bad tokens."""
        if not getattr(self, 'validlink', False):
            # Pass form=None so FormMixin does not build SetPasswordForm.
            kwargs.setdefault('form', None)
            context = super().get_context_data(**kwargs)
            context.update(
                {
                    'form': None,
                    'title': 'Password reset unsuccessful',
                    'validlink': False,
                }
            )
            log.warning(
                'password_reset_confirm_rejected reason=invalid_or_expired uidb64=%s user_id=%s',
                (self.kwargs.get('uidb64') or '')[:32],
                getattr(getattr(self, 'user', None), 'pk', None),
            )
            return context

        context = super().get_context_data(**kwargs)
        context['validlink'] = True
        return context
