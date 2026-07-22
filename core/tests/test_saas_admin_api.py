"""Admin SaaS stats API and commercial request approval.

TradeFlow admins monitor plan KPIs and approve Enterprise
commercial requests that upgrade company subscriptions.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import CompanyPlanCommercialRequest, SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription


@override_settings(
    STAFF_MFA_REQUIRED=False,
    SAAS_READ_ONLY_DEMO_USERNAME='',
)
class SaasAdminApiTests(TestCase):
    """Assert admin SaaS API auth and approve action."""

    def setUp(self):
        """Log in staff admin with TradeFlow admin role."""
        ensure_default_plans()
        self.admin = User.objects.create_user('admin_saas', password='x', is_staff=True)
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client = Client()
        self.client.force_login(self.admin)

    def test_stats_requires_admin(self):
        """Deny SaaS stats to non-admin buyers."""
        buyer = User.objects.create_user('buyer', password='x')
        UserProfile.objects.create(user=buyer, role='buyer')
        c = Client()
        c.force_login(buyer)
        r = c.get(reverse('api_admin_saas_stats'))
        self.assertIn(r.status_code, (302, 403))

    def test_stats_json_structure(self):
        """Return kpis, plan_usage, and predictive amount fields."""
        company = Company.objects.create(name='Empresa Test')
        ensure_demo_subscription(company)
        r = self.client.get(reverse('api_admin_saas_stats'))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('kpis', data)
        self.assertIn('plan_usage', data)
        self.assertIn('predictive', data)
        self.assertIn('predicted_amount_usd', data['predictive'])

    def test_approve_commercial_request(self):
        """Approve request and move company onto enterprise plan."""
        plan = SaasPlan.objects.get(slug='ecosistema_enterprise')
        company = Company.objects.create(name='Enterprise Co')
        ensure_demo_subscription(company)
        req = CompanyPlanCommercialRequest.objects.create(
            company=company,
            requested_plan=plan,
            contact_name='Ana',
            contact_email='ana@test.com',
            message='Necesito enterprise',
        )
        url = reverse('api_admin_saas_request_action', kwargs={'pk': req.pk})
        r = self.client.post(
            url,
            data='{"action":"approve"}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, 'approved')
        company.subscription.refresh_from_db()
        self.assertEqual(company.subscription.plan.slug, 'ecosistema_enterprise')


    def test_invalid_action_does_not_change_request(self):
        """Reject an unsupported action without changing stored state."""
        plan = SaasPlan.objects.get(slug='ecosistema_enterprise')
        company = Company.objects.create(name='Invalid Action Co')
        ensure_demo_subscription(company)
        request_row = CompanyPlanCommercialRequest.objects.create(
            company=company,
            requested_plan=plan,
            contact_name='Luis',
            contact_email='luis@test.com',
            message='Solicitud de prueba',
        )
        url = reverse(
            'api_admin_saas_request_action',
            kwargs={'pk': request_row.pk},
        )

        response = self.client.post(
            url,
            data='{"action":"archive"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid action'})
        request_row.refresh_from_db()
        self.assertEqual(request_row.status, 'pending')

    def test_unknown_request_returns_not_found(self):
        """Return a clear error when the commercial request does not exist."""
        url = reverse(
            'api_admin_saas_request_action',
            kwargs={'pk': 999999},
        )

        response = self.client.post(
            url,
            data='{"action":"approve"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'error': 'Application not found'},
        )

    def test_request_action_requires_post(self):
        """Reject GET requests so reads cannot trigger a state transition."""
        url = reverse(
            'api_admin_saas_request_action',
            kwargs={'pk': 1},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.json(),
            {'error': 'Method not allowed'},
        )
