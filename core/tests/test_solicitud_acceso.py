"""Tests for /solicitud-acceso/ (access + enterprise commercial application)."""
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import CompanyPlanCommercialRequest
from core.models import Company, UserApplication, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SolicitudAccesoTests(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.client = Client()

    def test_enterprise_page_loads(self):
        r = self.client.get(reverse('solicitud_acceso'), {'plan': 'enterprise'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ecosistema Enterprise')
        self.assertContains(r, 'name="email"')
        self.assertContains(r, 'name="requested_plan_slug"')
        self.assertContains(r, 'value="ecosistema_enterprise"', html=False)

    def test_legacy_corporate_email_field_still_works(self):
        """Bug fix: old template posted corporate_email; view must accept it."""
        r = self.client.post(
            reverse('solicitud_acceso') + '?plan=enterprise',
            {
                'full_name': 'Ada Seller',
                'corporate_email': 'ada@zlc-co.com',
                'phone': '+507 6000-1111',
                'company_name': 'ZLC Co',
                'ruc': '15566890-1-2020',
                'role': 'seller',
                'message': 'Need enterprise',
                'requested_plan_slug': 'ecosistema_enterprise',
            },
        )
        self.assertEqual(r.status_code, 302)
        app = UserApplication.objects.get(email='ada@zlc-co.com')
        self.assertEqual(app.status, 'pending')
        self.assertEqual(app.requested_plan_slug, 'ecosistema_enterprise')
        self.assertIn('RUC: 15566890-1-2020', app.message)

    def test_email_field_submits_application(self):
        r = self.client.post(
            reverse('solicitud_acceso') + '?plan=enterprise',
            {
                'full_name': 'Ben Buyer',
                'email': 'ben@import.com',
                'phone': '+507 6000-2222',
                'company_name': 'Import Co',
                'ruc': '8-NT-1',
                'role': 'buyer',
                'message': 'Volume growth',
                'requested_plan_slug': 'ecosistema_enterprise',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            UserApplication.objects.filter(
                email='ben@import.com',
                requested_plan_slug='ecosistema_enterprise',
            ).exists()
        )

    def test_authenticated_seller_creates_commercial_request(self):
        user = User.objects.create_user('ent_seller', password='x', email='ent@zlc.com')
        UserProfile.objects.create(user=user, role='seller', email_verificado=True)
        company = Company.objects.create(name='Ent Co', owner=user, ruc='8-ENT-1')
        ensure_demo_subscription(company, status='active')
        self.client.force_login(user)

        r = self.client.post(
            reverse('solicitud_acceso') + '?plan=enterprise',
            {
                'full_name': 'Ent Seller',
                'email': 'ent@zlc.com',
                'phone': '+507 6000-3333',
                'company_name': 'Ent Co',
                'ruc': '8-ENT-1',
                'role': 'seller',
                'message': 'API + unlimited SKUs',
                'requested_plan_slug': 'ecosistema_enterprise',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            CompanyPlanCommercialRequest.objects.filter(
                company=company,
                requested_plan__slug='ecosistema_enterprise',
                status='pending',
            ).exists()
        )

    def test_missing_email_does_not_create(self):
        r = self.client.post(
            reverse('solicitud_acceso'),
            {
                'full_name': 'No Email',
                'phone': '+507 6000-0000',
                'company_name': 'X',
                'ruc': '1',
                'role': 'buyer',
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(UserApplication.objects.filter(full_name='No Email').exists())
