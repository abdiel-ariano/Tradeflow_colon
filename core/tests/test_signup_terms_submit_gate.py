"""Regresión: el submit de signup no puede quedar disabled para siempre."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse


class SignupTermsSubmitGateSourceTests(SimpleTestCase):
    """El include de términos se renderiza ANTES del botón submit."""

    def test_terms_script_defers_submit_lookup_until_dom_ready(self):
        """Evita el race: script inline antes del botón dejaba submitBtn=null."""
        source = (
            Path(settings.BASE_DIR)
            / 'templates'
            / 'core'
            / 'includes'
            / 'signup_terms_consent.html'
        ).read_text(encoding='utf-8')
        self.assertIn('DOMContentLoaded', source)
        self.assertIn('getSubmitBtn', source)
        self.assertIn('button.auth-submit[type="submit"]', source)
        self.assertNotIn(
            "form.querySelector('.auth-submit')",
            source.split('function getSubmitBtn')[0],
        )

    def test_signup_template_includes_terms_before_submit_button(self):
        """Documenta el orden del DOM que provocó el bug original."""
        source = (
            Path(settings.BASE_DIR) / 'templates' / 'core' / 'signup_seller.html'
        ).read_text(encoding='utf-8')
        terms_at = source.index('signup_terms_consent.html')
        submit_at = source.index('class="auth-submit"')
        self.assertLess(terms_at, submit_at)
        self.assertIn('disabled', source[submit_at:submit_at + 40])
        self.assertIn('Company name', source)
        self.assertNotIn('name="last_name"', source)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class SignupCompanyNameFlowTests(TestCase):
    """Company name (POST first_name) + terms gate en el registro unificado."""

    def setUp(self):
        self.client = Client()

    def test_signup_page_renders_company_name_and_gated_submit(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('name="first_name"', html)
        self.assertIn('Company name', html)
        self.assertIn('id_terms_accepted', html)
        self.assertIn('required', html)
        self.assertIn('auth-submit', html)
        self.assertIn('disabled', html)
        self.assertIn('Continue to company verification', html)
        self.assertIn('DOMContentLoaded', html)
        self.assertIn('getSubmitBtn', html)

    def test_signup_rejects_missing_terms(self):
        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'Acme Free Zone SA',
                'username': 'acmebuyer',
                'email': 'acmebuyer@example.com',
                'phone': '',
                'business_role': 'buyer',
                'password1': 'SecurePass9!',
                'password2': 'SecurePass9!',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Debes aceptar los Términos de Uso y la Política de Seguridad',
        )

    def test_signup_accepts_company_name_with_terms(self):
        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'Acme Free Zone SA',
                'username': 'acmeseller',
                'email': 'acmeseller@example.com',
                'phone': '+50760000000',
                'business_role': 'both',
                'password1': 'SecurePass9!',
                'password2': 'SecurePass9!',
                'terms_accepted': '1',
            },
        )
        self.assertIn(response.status_code, (302, 200))
        if response.status_code == 302:
            self.assertNotEqual(response.url, reverse('signup'))
        from django.contrib.auth.models import User

        user = User.objects.filter(username='acmeseller').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Acme Free Zone SA')
