"""Company verification tracking: admin prioritization and applicant polling."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Company, UserApplication, UserProfile
from core.utils.admin_permissions import sync_user_admin_access


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    EXPO_DEMO_MODE=False,
    STAFF_MFA_REQUIRED=False,
)
class CompanyVerificationTrackingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='verify.admin',
            email='verify.admin@test',
            password='Pass12345!',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        sync_user_admin_access(self.admin)

        self.owner = User.objects.create_user(
            username='verify.owner',
            email='owner@empresa.test',
            password='Pass12345!',
        )
        UserProfile.objects.create(
            user=self.owner,
            role='seller',
            email_verificado=True,
            business_role_intent='seller',
        )

    def _pending_company(self, **overrides) -> Company:
        data = {
            'name': 'Pending Co',
            'legal_name': 'Pending Co SA',
            'ruc': '8-PENDING-TRACK-1',
            'dv': '12',
            'business_email': 'empresa@pending.test',
            'business_phone': '+50760000000',
            'business_role': 'seller',
            'address_text': 'ZLC',
            'owner': self.owner,
            'verification_document': 'companies/verification/aviso.pdf',
            'verification_status': 'pending',
            'verification_submitted_at': timezone.now(),
        }
        data.update(overrides)
        return Company.objects.create(**data)

    def test_default_companies_list_prioritizes_pending_recent_first(self):
        verified = self._pending_company(
            ruc='8-VERIFIED-1',
            name='Verified Co',
            verification_status='verified',
            verification_submitted_at=timezone.now() - timedelta(days=3),
        )
        older_pending = self._pending_company(
            ruc='8-PENDING-OLD',
            name='Older Pending',
            verification_submitted_at=timezone.now() - timedelta(days=2),
        )
        newer_pending = self._pending_company(
            ruc='8-PENDING-NEW',
            name='Newer Pending',
            verification_submitted_at=timezone.now() - timedelta(hours=1),
        )

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('lista_empresas'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('empresa', body)
        self.assertIn('pendiente', body.lower())
        self.assertIn('Revisar', body)
        self.assertLess(
            body.index('Newer Pending'),
            body.index('Older Pending'),
        )
        self.assertLess(
            body.index('Older Pending'),
            body.index('Verified Co'),
        )

    def test_companies_list_respects_explicit_sort(self):
        self._pending_company(ruc='8-SORT-A', name='Alpha Pending')
        self._pending_company(ruc='8-SORT-B', name='Beta Pending')
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('lista_empresas'), {'orden': 'nombre'})
        body = resp.content.decode()
        self.assertLess(body.index('Alpha Pending'), body.index('Beta Pending'))

    def test_pending_filter_shows_only_pending(self):
        self._pending_company(ruc='8-ONLY-PEND')
        self._pending_company(
            ruc='8-ONLY-VER',
            verification_status='verified',
            name='Verified Only',
        )
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('lista_empresas'), {'estado': 'pending'})
        body = resp.content.decode()
        self.assertIn('Pending Co', body)
        self.assertNotIn('Verified Only', body)

    def test_admin_pending_watch_api_is_read_only_json(self):
        company = self._pending_company()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('api_admin_companies_pending_watch'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')
        payload = resp.json()
        self.assertGreaterEqual(payload['pending_count'], 1)
        self.assertTrue(any(item['id'] == company.pk for item in payload['submissions']))

    def test_owner_poll_returns_pending_and_does_not_mutate(self):
        company = self._pending_company()
        owner_client = Client()
        owner_client.force_login(self.owner)
        resp = owner_client.get(reverse('api_company_verification_status'))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['verification_status'], 'pending')
        self.assertTrue(payload['poll_active'])
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')

    def test_owner_poll_reflects_verification_without_reload(self):
        company = self._pending_company()
        owner_client = Client()
        owner_client.force_login(self.owner)

        company.mark_verified(self.admin)
        resp = owner_client.get(reverse('api_company_verification_status'))
        payload = resp.json()
        self.assertEqual(payload['verification_status'], 'verified')
        self.assertFalse(payload['poll_active'])
        self.assertEqual(payload['continue_url'], reverse('company_onboarding'))

    def test_owner_cannot_poll_foreign_company(self):
        outsider = User.objects.create_user('outsider', password='x')
        UserProfile.objects.create(
            user=outsider,
            role='seller',
            email_verificado=True,
            business_role_intent='seller',
        )
        self._pending_company()
        client = Client()
        client.force_login(outsider)
        resp = client.get(reverse('api_company_verification_status'))
        self.assertEqual(resp.status_code, 404)

    @override_settings(REQUIRE_APPROVED_APPLICATION=True)
    def test_verified_company_with_pending_application_reports_access_block(self):
        buyer = User.objects.create_user(
            username='verify.buyer',
            email='buyer@empresa.test',
            password='Pass12345!',
        )
        UserProfile.objects.create(
            user=buyer,
            role='buyer',
            email_verificado=True,
            business_role_intent='buyer',
        )
        company = Company.objects.create(
            name='Buyer Pending Co',
            legal_name='Buyer Pending Co SA',
            ruc='8-BUYER-PEND',
            dv='12',
            business_email='buyer@empresa.test',
            business_phone='+50760000000',
            business_role='buyer',
            address_text='ZLC',
            owner=buyer,
            verification_document='companies/verification/aviso.pdf',
            verification_status='pending',
            verification_submitted_at=timezone.now(),
        )
        UserApplication.objects.create(
            email=buyer.email,
            full_name='Buyer',
            company_name=company.name,
            status='pending',
        )
        company.mark_verified(self.admin)

        owner_client = Client()
        owner_client.force_login(buyer)
        payload = owner_client.get(
            reverse('api_company_verification_status'),
        ).json()
        self.assertEqual(payload['verification_status'], 'verified')
        self.assertIsNotNone(payload['access_block'])
        self.assertEqual(
            payload['continue_url'],
            reverse('onboarding_espera_aprobacion'),
        )

    def test_status_page_includes_poll_script_for_pending(self):
        self._pending_company()
        owner_client = Client()
        owner_client.force_login(self.owner)
        resp = owner_client.get(reverse('company_verification_status'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('data-poll-url', body)
        self.assertIn('company_verification_poll.js', body)
        self.assertIn('cada 10 segundos', body)

    def test_admin_rail_shows_separate_companies_pending_badge(self):
        self._pending_company()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('lista_empresas'))
        body = resp.content.decode()
        self.assertIn('adm-companies-pending-badge', body)
