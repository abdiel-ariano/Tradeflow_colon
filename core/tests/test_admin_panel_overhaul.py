"""Admin panel overhaul: ops rail, work queue, safe mutations, dense dirs."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Company, Product, Transportista, UserProfile
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
class AdminPanelOverhaulTests(TestCase):
    """P0/P1 operator console regressions."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='ops.admin',
            email='ops@tradeflow.test',
            password='Pass12345!',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        sync_user_admin_access(self.admin)
        self.client.force_login(self.admin)

    def test_rail_points_to_ops_routes(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('id="admRail"', body)
        self.assertIn('/ordenes/', body)
        self.assertIn('/productos/', body)
        self.assertIn('/empresas/', body)
        self.assertIn('/panel/applications/', body)
        self.assertIn('/panel/carriers/', body)
        self.assertIn('Needs attention', body)

    def test_carriers_use_shell_and_reject_get_mutation(self):
        t = Transportista.objects.create(
            empresa_nombre='ZLC Haul',
            licencia='LIC-1',
            telefono='60000000',
            email_contacto='haul@test.pa',
            vehiculo_tipo='truck',
            vehiculo_placa='ABC-123',
            cobertura_descripcion='Colón',
            tarifa_base='25.00',
            estado='pendiente',
        )
        list_resp = self.client.get(reverse('admin_transportistas'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'id="admRail"')
        self.assertContains(list_resp, 'ZLC Haul')

        get_mut = self.client.get(
            reverse('admin_aprobar_transportista', args=[t.pk, 'aprobar'])
        )
        self.assertEqual(get_mut.status_code, 405)
        t.refresh_from_db()
        self.assertEqual(t.estado, 'pendiente')

        post_mut = self.client.post(
            reverse('admin_aprobar_transportista', args=[t.pk, 'aprobar'])
        )
        self.assertEqual(post_mut.status_code, 302)
        t.refresh_from_db()
        self.assertEqual(t.estado, 'aprobado')

    def test_company_search_verify_and_detail(self):
        company = Company.objects.create(name='Verify Co', ruc='8-VERIFY-1')
        list_resp = self.client.get(reverse('lista_empresas'), {'buscar': 'Verify'})
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'Verify Co')

        toggle = self.client.post(
            reverse('admin_toggle_company_verified', args=[company.pk]),
            {'next': reverse('lista_empresas')},
        )
        self.assertEqual(toggle.status_code, 302)
        company.refresh_from_db()
        self.assertTrue(company.is_verified)

        detail = self.client.get(reverse('admin_empresa_detalle', args=[company.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Verify Co')
        self.assertContains(detail, 'id="admRail"')

    def test_panel_search_and_products_table(self):
        company = Company.objects.create(name='Search Co', ruc='8-SEARCH-1')
        Product.objects.create(
            company=company,
            name='Dense SKU Widget',
            unit_price='10.00',
            is_active=True,
        )
        search = self.client.get(reverse('admin_panel_search'), {'q': 'Search'})
        self.assertEqual(search.status_code, 200)
        self.assertContains(search, 'Search Co')

        products = self.client.get(reverse('lista_productos'))
        self.assertEqual(products.status_code, 200)
        self.assertContains(products, 'Dense SKU Widget')
        self.assertContains(products, '<table class="adm-table">')
        self.assertContains(products, 'Deactivate')

    def test_ops_visual_contract_is_unified(self):
        """Ops pages share brand CSS and stay inside the panel flow."""
        dash = self.client.get(reverse('dashboard'))
        self.assertEqual(dash.status_code, 200)
        body = dash.content.decode()
        self.assertIn('tradeflow_admin_ops.css', body)
        self.assertNotIn('Advanced CRUD', body)
        self.assertNotIn('Advanced create', body)
        self.assertNotIn('title="Marketplace"', body)
        self.assertIn('tf-admin-unified', body)
        self.assertIn('data-rail-accordion="multi"', body)
        self.assertNotIn('admRailToggle', body)
        self.assertNotIn('Collapse', body)

        products = self.client.get(reverse('lista_productos'))
        self.assertEqual(products.status_code, 200)
        self.assertNotContains(products, 'Advanced create')
        self.assertNotContains(products, 'adm-btn--advanced')

    def test_admin_index_routes_to_ops_dashboard(self):
        """/admin/ is not a second control panel — it hands off to ops."""
        resp = self.client.get(reverse('admin:index'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))
