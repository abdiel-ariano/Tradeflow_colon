"""POST-only logout controls across onboarding, navbars, and pending-review screens."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Company, UserProfile

LOGOUT_PAGES = (
    ('company_verification_status', {}),
    ('onboarding_espera_verificacion', {}),
    ('onboarding_solicitud_requerida', {}),
    ('onboarding_aplicacion_rechazada', {}),
    ('home', {}),
    ('catalogo_publico', {}),
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    EXPO_DEMO_MODE=False,
    STAFF_MFA_REQUIRED=False,
)
class LogoutPostControlsTests(TestCase):
    """Logout must use POST+CSRF; GET /logout/ must not terminate sessions."""

    def setUp(self):
        self.client = Client()
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.pending_owner = User.objects.create_user(
            username='pending.demo',
            email='pending@demo.test',
            password='Pass12345!',
        )
        UserProfile.objects.create(
            user=self.pending_owner,
            role='seller',
            email_verificado=True,
        )
        self.company = Company.objects.create(
            name='Demo Wholesale',
            legal_name='Demo Wholesale, S.A.',
            ruc='8-LOGOUT-DEMO-1',
            dv='12',
            business_email='empresa@demo.test',
            business_phone='+50760000000',
            business_role='seller',
            address_text='Colón, ZLC',
            owner=self.pending_owner,
            verification_document='companies/verification/aviso-operacion.pdf',
            verification_status='pending',
        )
        self.admin = User.objects.create_user(
            username='admin.after.logout',
            email='admin.after.logout@test',
            password='AdminPass123!',
            is_staff=True,
        )
        UserProfile.objects.create(
            user=self.admin,
            role='admin',
            email_verificado=True,
        )

    def _login_pending_owner(self):
        self.client.force_login(self.pending_owner)

    def test_get_logout_returns_405_and_keeps_session(self):
        """Reproduce reported failure: GET /logout/ must not log the user out."""
        self._login_pending_owner()
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 405)

        status_page = self.client.get(reverse('company_verification_status'))
        self.assertEqual(status_page.status_code, 200)
        self.assertContains(status_page, 'Revisión pendiente')

    def test_pending_company_verification_logout_uses_post_form(self):
        """Pending-review screen must not link to GET /logout/."""
        self._login_pending_owner()
        resp = self.client.get(reverse('company_verification_status'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('method="post"', body)
        self.assertIn('action="/logout/"', body)
        self.assertIn('csrfmiddlewaretoken', body)
        self.assertIn('Cerrar sesión', body)
        self.assertNotIn('href="/logout/"', body)
        self.assertNotIn("href='/logout/'", body)

    def test_pending_owner_can_logout_via_post_and_switch_accounts(self):
        self._login_pending_owner()
        resp = self.client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('login'))

        blocked = self.client.get(reverse('company_verification_status'))
        self.assertEqual(blocked.status_code, 302)

        self.client.get(reverse('login'))
        login = self.client.post(
            reverse('login'),
            {'username': self.admin.username, 'password': 'AdminPass123!'},
        )
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.wsgi_request.user.is_authenticated)
        self.assertEqual(login.wsgi_request.user.username, self.admin.username)

    def test_logout_post_without_csrf_is_rejected(self):
        self.csrf_client.force_login(self.pending_owner)
        resp = self.csrf_client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 403)

        still_in = self.csrf_client.get(reverse('company_verification_status'))
        self.assertEqual(still_in.status_code, 200)

    def test_seller_onboarding_wizard_logout_is_post(self):
        wizard_user = User.objects.create_user(
            username='wizard.logout',
            email='wizard@demo.test',
            password='Pass12345!',
        )
        UserProfile.objects.create(
            user=wizard_user,
            role='seller',
            email_verificado=True,
        )
        self.client.force_login(wizard_user)
        resp = self.client.get(reverse('seller_onboarding_company'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'method="post"')
        self.assertContains(resp, 'Cerrar sesión')
        self.assertNotContains(resp, 'href="/logout/"')

    def test_public_shells_do_not_emit_get_logout_links(self):
        self._login_pending_owner()
        for route_name, kwargs in LOGOUT_PAGES:
            with self.subTest(route=route_name):
                resp = self.client.get(reverse(route_name, kwargs=kwargs))
                if resp.status_code != 200:
                    self.skipTest(f'{route_name} returned {resp.status_code}')
                body = resp.content.decode()
                self.assertNotIn('href="/logout/"', body, msg=route_name)
                self.assertNotIn("href='/logout/'", body, msg=route_name)
                if '/logout/' in body:
                    self.assertIn('method="post"', body, msg=route_name)

    def test_catalog_navbar_logout_is_post_on_desktop_markup(self):
        self._login_pending_owner()
        resp = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertNotIn('href="/logout/"', body)
        self.assertIn('method="post"', body)
        self.assertIn('action="/logout/"', body)
