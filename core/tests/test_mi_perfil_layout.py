"""Profile page layout, tabs, and form behavior."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Company, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class MiPerfilLayoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='layout.profile',
            email='layout.profile@very-long-email-address-for-wrap.testing.pa',
            password='Pass12345!',
            first_name='VeryLongFirstName',
            last_name='VeryLongLastName',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        Company.objects.create(
            name='Layout Profile Co',
            legal_name='Layout Profile Co, S.A.',
            ruc='8-LAYOUT-PROFILE',
            dv='12',
            business_email='layout.profile@very-long-email-address-for-wrap.testing.pa',
            verification_document='companies/verification/aviso.pdf',
            owner=self.user,
            business_role='buyer',
            verification_status='verified',
        )
        self.client.force_login(self.user)

    def test_profile_uses_wide_shell_and_tabs(self):
        resp = self.client.get(reverse('mi_perfil'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('perfil-shell', body)
        self.assertIn('mi-perfil.css', body)
        self.assertIn('perfil-tabs', body)
        self.assertIn('Personal information', body)

    def test_password_fields_have_clear_labels_and_button(self):
        resp = self.client.get(reverse('mi_perfil'), {'tab': 'security'})
        body = resp.content.decode()
        self.assertIn('Current password', body)
        self.assertIn('New password', body)
        self.assertIn('Confirm new password', body)
        self.assertIn('Change password', body)
        self.assertContains(resp, 'data-target="pf_current"')
        self.assertContains(resp, 'data-target="pf_new"')
        self.assertContains(resp, 'data-target="pf_confirm"')

    def test_sign_out_uses_post_logout_control(self):
        resp = self.client.get(reverse('mi_perfil'))
        body = resp.content.decode()
        self.assertIn('method="post"', body)
        self.assertIn('action="/logout/"', body)
        self.assertIn('Sign out', body)
        self.assertNotIn('href="/logout/"', body)

    def test_update_info_redirects_to_personal_tab(self):
        resp = self.client.post(
            reverse('mi_perfil'),
            {
                'action': 'update_info',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'email': self.user.email,
                'phone': '555',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=personal', resp.url)

    def test_password_error_opens_security_tab_with_field_error(self):
        resp = self.client.post(
            reverse('mi_perfil'),
            {
                'action': 'change_password',
                'current_password': 'wrong',
                'new_password': 'NewPass123!',
                'confirm_password': 'NewPass123!',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=security', resp.url)
        follow = self.client.get(resp.url)
        self.assertContains(follow, 'Current password is incorrect.')

    def test_long_name_and_email_render_without_overflow_styles(self):
        resp = self.client.get(reverse('mi_perfil'))
        body = resp.content.decode()
        self.assertIn('VeryLongFirstName', body)
        self.assertIn('layout.profile@very-long-email-address-for-wrap.testing.pa', body)
        self.assertIn('mi-perfil.css', body)
