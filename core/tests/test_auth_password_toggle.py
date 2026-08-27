"""Password visibility toggle on auth-related forms."""
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
class AuthPasswordToggleTests(TestCase):
    """Ensure show/hide password controls exist and target the right inputs."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='profile.user',
            email='profile@test.pa',
            password='Pass12345!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        Company.objects.create(
            name='Profile Toggle Co',
            legal_name='Profile Toggle Co, S.A.',
            ruc='8-PROFILE-TOGGLE',
            dv='12',
            business_email='profile@test.pa',
            verification_document='companies/verification/aviso-operacion.pdf',
            owner=self.user,
            business_role='buyer',
            verification_status='verified',
        )

    def test_login_has_password_toggle_for_password_field(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_password"')
        self.assertContains(response, 'js-password-toggle')
        self.assertContains(response, 'data-target="id_password"')
        self.assertContains(response, 'auth-password-toggle.js')

    def test_signup_buyer_has_toggles_for_both_password_fields(self):
        response = self.client.get(reverse('signup_buyer'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-target="id_password1"')
        self.assertContains(response, 'data-target="id_password2"')
        self.assertContains(response, 'type="button"')
        self.assertContains(response, 'aria-pressed="false"')

    def test_signup_seller_has_toggles_for_both_password_fields(self):
        response = self.client.get(reverse('signup_seller'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-target="id_password1"')
        self.assertContains(response, 'data-target="id_password2"')

    def test_profile_change_password_has_three_toggles(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('mi_perfil'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-target="pf_current"')
        self.assertContains(response, 'data-target="pf_new"')
        self.assertContains(response, 'data-target="pf_confirm"')

    def test_password_reset_confirm_has_toggles_when_link_valid(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from core.utils.password_reset_link import generate_password_reset_link

        token = generate_password_reset_link(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token},
        )
        first = self.client.get(confirm_url)
        self.assertEqual(first.status_code, 302)
        set_url = first.url
        response = self.client.get(set_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-target="id_new_password1"')
        self.assertContains(response, 'data-target="id_new_password2"')
        self.assertContains(response, 'auth-password-toggle.js')
