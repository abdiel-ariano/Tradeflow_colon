"""Admin POST toggle for B2B company verification (canonical verification_status)."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from core.models import Company, UserProfile
from core.utils.admin_permissions import sync_user_admin_access
from core.views.admin_ops import admin_toggle_company_verified


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    STAFF_MFA_REQUIRED=False,
    EXPO_DEMO_MODE=False,
)
class AdminCompanyVerificationToggleTests(TestCase):
    """Cover Admin Panel → Companies Verify button and canonical state."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='company.reviewer',
            email='reviewer@tradeflow.test',
            password='Pass12345!',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        sync_user_admin_access(self.admin)
        self.client.force_login(self.admin)

        self.buyer_user = User.objects.create_user(
            username='buyer_owner',
            email='owner@empresa.pa',
            password='Pass12345!',
        )
        UserProfile.objects.create(
            user=self.buyer_user,
            role='buyer',
            email_verificado=True,
        )

    def _complete_pending_company(self, **overrides) -> Company:
        data = {
            'name': 'Wholesale Demo Co',
            'legal_name': 'Wholesale Demo Co, S.A.',
            'ruc': '8-ADMIN-VERIFY-1',
            'dv': '12',
            'business_email': 'empresa@demo.test',
            'business_phone': '+50760000000',
            'business_role': 'buyer',
            'address_text': 'Colón, ZLC, Local demo 12',
            'owner': self.buyer_user,
            'verification_document': 'companies/verification/aviso-operacion.pdf',
            'verification_status': 'pending',
        }
        data.update(overrides)
        return Company.objects.create(**data)

    def test_url_resolves_to_admin_toggle_view(self):
        match = resolve(reverse('admin_toggle_company_verified', args=[1]))
        self.assertEqual(match.func, admin_toggle_company_verified)

    def test_companies_list_verify_button_post_verifies_company(self):
        """Reproduce Admin Panel → Companies list Verify action."""
        company = self._complete_pending_company()
        list_url = reverse('lista_empresas')
        toggle_url = reverse('admin_toggle_company_verified', args=[company.pk])

        list_before = self.client.get(list_url)
        self.assertEqual(list_before.status_code, 200)
        self.assertContains(list_before, 'Verify')
        self.assertContains(list_before, toggle_url)

        response = self.client.post(toggle_url, {'next': list_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, list_url)

        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'verified')
        self.assertTrue(company.is_verified)
        self.assertEqual(company.verified_by, self.admin)
        self.assertIsNotNone(company.verified_at)

        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('marked verified' in m for m in msgs))

        list_after = self.client.get(list_url)
        self.assertEqual(list_after.status_code, 200)
        self.assertContains(list_after, 'Unverify')
        self.assertContains(list_after, company.name)

    def test_get_is_not_allowed(self):
        company = self._complete_pending_company()
        response = self.client.get(
            reverse('admin_toggle_company_verified', args=[company.pk]),
        )
        self.assertEqual(response.status_code, 405)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)

    def test_non_admin_cannot_verify(self):
        outsider = User.objects.create_user('outsider', password='x')
        UserProfile.objects.create(user=outsider, role='buyer', email_verificado=True)
        self.client.force_login(outsider)

        company = self._complete_pending_company(ruc='8-ADMIN-DENY')
        response = self.client.post(
            reverse('admin_toggle_company_verified', args=[company.pk]),
        )
        self.assertIn(response.status_code, (302, 403))
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)

    def test_incomplete_company_keeps_state_and_shows_error(self):
        company = Company.objects.create(
            name='Incomplete Wholesale',
            legal_name='Incomplete Wholesale, S.A.',
            ruc='8-ADMIN-INCOMPLETE',
            verification_status='pending',
        )
        response = self.client.post(
            reverse('admin_toggle_company_verified', args=[company.pk]),
            {'next': reverse('lista_empresas')},
        )
        self.assertEqual(response.status_code, 302)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)

        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('Cannot verify' in m for m in msgs))
        self.assertFalse(any('marked unverified' in m.lower() for m in msgs))

    def test_verified_company_can_unverify_from_list(self):
        company = self._complete_pending_company(ruc='8-ADMIN-UNVERIFY')
        company.mark_verified(self.admin)

        response = self.client.post(
            reverse('admin_toggle_company_verified', args=[company.pk]),
            {'next': reverse('lista_empresas')},
        )
        self.assertEqual(response.status_code, 302)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)
        self.assertIsNone(company.verified_by)
        self.assertIsNone(company.verified_at)

    def test_admin_detail_matches_verification_status(self):
        company = self._complete_pending_company(ruc='8-ADMIN-DETAIL')
        self.client.post(
            reverse('admin_toggle_company_verified', args=[company.pk]),
            {'next': reverse('admin_empresa_detalle', args=[company.pk])},
        )
        detail = self.client.get(reverse('admin_empresa_detalle', args=[company.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Verified')
        self.assertContains(detail, 'Unverify')

    def test_onboarding_status_page_leaves_pending_review_after_verify(self):
        company = self._complete_pending_company(ruc='8-ADMIN-ONBOARD')
        company.mark_verified(self.admin)

        owner_client = Client()
        owner_client.force_login(self.buyer_user)
        response = owner_client.get(reverse('company_verification_status'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Estamos revisando la empresa')
        self.assertContains(response, 'Empresa verificada')

    def test_no_view_toggles_is_verified_directly(self):
        """Regression guard: admin code must not flip is_verified in isolation."""
        import pathlib
        import re

        admin_ops = pathlib.Path('core/views/admin_ops.py').read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'is_verified\s*=\s*not', admin_ops))
        self.assertIsNone(re.search(r"update_fields=\['is_verified'\]", admin_ops))
