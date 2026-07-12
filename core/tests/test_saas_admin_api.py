"""API panel admin SaaS."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.enterprise_models import CompanyPlanCommercialRequest, SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, get_or_create_subscription


class SaasAdminApiTests(TestCase):
    def setUp(self):
        """Setup."""
        ensure_default_plans()
        self.admin = User.objects.create_user('admin_saas', password='x', is_staff=True)
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client = Client()
        self.client.force_login(self.admin)

    def test_stats_requires_admin(self):
        """Test stats requires admin."""
        buyer = User.objects.create_user('buyer', password='x')
        UserProfile.objects.create(user=buyer, role='buyer')
        c = Client()
        c.force_login(buyer)
        r = c.get(reverse('api_admin_saas_stats'))
        self.assertIn(r.status_code, (302, 403))

    def test_stats_json_structure(self):
        """Test stats json structure."""
        company = Company.objects.create(name='Empresa Test')
        get_or_create_subscription(company)
        r = self.client.get(reverse('api_admin_saas_stats'))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('kpis', data)
        self.assertIn('plan_usage', data)
        self.assertIn('predictive', data)
        self.assertIn('predicted_amount_usd', data['predictive'])

    def test_approve_commercial_request(self):
        """Test approve commercial request."""
        plan = SaasPlan.objects.get(slug='ecosistema_enterprise')
        company = Company.objects.create(name='Enterprise Co')
        get_or_create_subscription(company)
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
