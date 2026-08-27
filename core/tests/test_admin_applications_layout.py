"""Admin Access Applications page: responsive layout and action controls."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserApplication, UserProfile
from core.utils.admin_permissions import sync_user_admin_access


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    STAFF_MFA_REQUIRED=False,
    EXPO_DEMO_MODE=False,
)
class AdminApplicationsLayoutTests(TestCase):
    """Applications screen loads, filters work, and layout stays responsive."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='apps.admin',
            email='apps.admin@tradeflow.test',
            password='Pass12345!',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        sync_user_admin_access(self.admin)
        self.client.force_login(self.admin)

        self.pending = UserApplication.objects.create(
            full_name='Pending Applicant',
            email='pending.applicant.with.a.very.long.email.address@example-company-domain.test',
            company_name='Long Company Name International Holdings Group',
            phone='+507 6000-0000 ext. 12345',
            role='seller',
            message='We would like access to the marketplace for our export operations.',
            status='pending',
        )
        UserApplication.objects.create(
            full_name='Approved Applicant',
            email='approved@example.com',
            company_name='Approved Co',
            role='buyer',
            status='approved',
        )

    def test_applications_page_loads_with_responsive_table_container(self):
        resp = self.client.get(reverse('admin_applications'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Access Applications', body)
        self.assertIn('adm-apps-page', body)
        self.assertIn('adm-apps-table-scroll', body)
        self.assertIn('id="adm-apps-table-card"', body)
        self.assertIn('overflow-x: auto', body)
        self.assertIn('min-width: 0', body)
        self.assertIn('adm-apps-col-actions', body)
        self.assertIn('adm-apps-scroll-hint', body)
        self.assertIn('Swipe horizontally to view all columns', body)
        self.assertIn('adm-apps-col-phone', body)
        self.assertIn('adm-apps-col-message', body)
        self.assertIn('adm-apps-col-status', body)
        self.assertIn('min-width: 1460px', body)
        self.assertNotIn('break-all', body)
        self.assertIn('Pending Applicant', body)

    def test_status_filters_remain_available(self):
        all_resp = self.client.get(reverse('admin_applications'))
        pending_resp = self.client.get(
            reverse('admin_applications'),
            {'status': 'pending'},
        )
        approved_resp = self.client.get(
            reverse('admin_applications'),
            {'status': 'approved'},
        )
        self.assertEqual(all_resp.status_code, 200)
        self.assertEqual(pending_resp.status_code, 200)
        self.assertEqual(approved_resp.status_code, 200)
        self.assertContains(pending_resp, 'Pending Applicant')
        self.assertNotContains(pending_resp, 'Approved Applicant')
        self.assertContains(approved_resp, 'Approved Applicant')
        self.assertNotContains(approved_resp, 'Pending Applicant')
        self.assertContains(all_resp, 'Search by name or email')
        self.assertContains(all_resp, 'id="adm-apps-export"')

    def test_pending_row_renders_approve_and_reject_actions(self):
        resp = self.client.get(
            reverse('admin_applications'),
            {'status': 'pending'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Approve')
        self.assertContains(resp, 'Reject')
        self.assertContains(resp, 'adm-apps-actions-cell')
        self.assertContains(
            resp,
            reverse('approve_application', args=[self.pending.pk]),
        )
        self.assertContains(
            resp,
            reverse('reject_application', args=[self.pending.pk]),
        )

    def test_approve_get_does_not_mutate_application(self):
        """Approval logic stays POST-only (no accidental GET mutation)."""
        url = reverse('approve_application', args=[self.pending.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'pending')

    def test_long_email_has_accessible_title_attribute(self):
        resp = self.client.get(reverse('admin_applications'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            f'title="{self.pending.email}"',
        )
