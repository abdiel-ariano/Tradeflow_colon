"""Admin topbar logout placement and POST-only session termination."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from core.utils.admin_permissions import sync_user_admin_access

ADMIN_PAGES = (
    ('dashboard', {}),
    ('lista_empresas', {}),
    ('admin_applications', {}),
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    STAFF_MFA_REQUIRED=False,
    EXPO_DEMO_MODE=False,
)
class AdminTopbarLogoutTests(TestCase):
    """Logout lives in the shared admin topbar with a secure POST form."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='topbar.admin',
            email='topbar.admin@tradeflow.test',
            password='Pass12345!',
            is_staff=True,
            first_name='Top',
            last_name='Bar',
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        sync_user_admin_access(self.admin)
        self.client.force_login(self.admin)

    def _logout_form_snippet(self, body: str) -> str:
        start = body.index('id="logout-form"')
        return body[start:start + 500]

    def test_admin_pages_render_single_topbar_logout_form(self):
        for route_name, kwargs in ADMIN_PAGES:
            with self.subTest(route=route_name):
                resp = self.client.get(reverse(route_name, kwargs=kwargs))
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode()
                self.assertEqual(body.count('id="logout-form"'), 1)
                self.assertIn('admin-topbar', body)
                self.assertIn('tf-admin-header__leading', body)
                snippet = self._logout_form_snippet(body)
                self.assertIn('method="post"', snippet)
                self.assertIn('csrfmiddlewaretoken', snippet)
                self.assertIn('Log out', body)
                self.assertIn('aria-label="Log out"', body)
                self.assertIn('title="Log out"', body)

    def test_dashboard_does_not_render_content_area_logout_link(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertNotIn('href="/logout/"', body)
        self.assertNotIn("href='/logout/'", body)
        self.assertIn('CFZ sales dashboard', body)
        self.assertIn('id="adm-dias-pills"', body)

    def test_logout_get_does_not_end_session(self):
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 405)
        dash = self.client.get(reverse('dashboard'))
        self.assertEqual(dash.status_code, 200)

    def test_logout_post_ends_session_and_redirects_to_login(self):
        resp = self.client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('login'))
        follow = self.client.get(reverse('dashboard'))
        self.assertEqual(follow.status_code, 302)
