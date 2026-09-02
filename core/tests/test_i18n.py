"""i18n coverage and language switching tests."""
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
class I18nLanguageSwitchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='i18n.buyer',
            email='i18n.buyer@test',
            password='Pass12345!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        Company.objects.create(
            name='I18n Test Co',
            legal_name='I18n Test Co, S.A.',
            ruc='8-I18N-TEST',
            dv='12',
            business_email=self.user.email,
            verification_document='companies/verification/aviso.pdf',
            owner=self.user,
            business_role='buyer',
            verification_status='verified',
        )

    def _activate_language(self, lang: str, next_path: str = '/'):
        return self.client.post(
            reverse('set_language'),
            {'language': lang, 'next': next_path},
        )

    def test_spanish_login_page_renders_spanish_copy(self):
        self._activate_language('es', '/es/login/')
        resp = self.client.get('/es/login/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Iniciar sesión', body)

    def test_english_login_page_renders_english_copy(self):
        self._activate_language('en', '/login/')
        resp = self.client.get('/login/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Sign in', body)
        self.assertNotIn('Iniciar sesión', body)

    def test_profile_page_respects_spanish(self):
        self.client.force_login(self.user)
        self._activate_language('es', '/es/perfil/')
        resp = self.client.get('/es/perfil/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Información personal', body)
        self.assertNotIn('>Personal information<', body)

    def test_footer_language_switcher_uses_post_forms(self):
        self._activate_language('en', '/')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('/i18n/setlang', body)
        self.assertIn('name="language"', body)
        self.assertNotIn('Spanish — coming soon', body)

    def test_tf_i18n_payload_includes_order_status_keys(self):
        self.client.force_login(self.user)
        self._activate_language('en', '/perfil/')
        resp = self.client.get('/perfil/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'orderStatus_pending')
