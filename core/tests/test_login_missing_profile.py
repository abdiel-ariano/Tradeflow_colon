"""Regression: login must not 500 when UserProfile is missing.

``base.html`` used to read ``request.user.profile.role`` directly. After
password or OAuth login, incomplete accounts hit RelatedObjectDoesNotExist
and Django returned HTTP 500 on the first shell page.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile


@override_settings(
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class LoginMissingProfileTests(TestCase):
    """Authenticated users without a profile must get a soft landing, not 500."""

    def setUp(self):
        """Create a password user with no ``UserProfile`` row."""
        self.user = User.objects.create_user(
            username='orphan_login',
            email='orphan@tradeflow.pa',
            password='Demo1234!',
        )
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_login_post_redirects_to_oauth_complete_not_500(self):
        """POST /login/ with a profile-less user redirects to role completion."""
        response = self.client.post(
            reverse('login'),
            {'username': 'orphan_login', 'password': 'Demo1234!'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('oauth_complete_signup'))

    def test_catalog_with_orphan_session_is_not_500(self):
        """Catalog/onboarding shell must not 500 when the session has no profile."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('catalogo_publico'), follow=True)
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'RelatedObjectDoesNotExist', response.content)

    def test_oauth_complete_signup_with_orphan_session_is_not_500(self):
        """Role-completion page itself must not crash on missing profile."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('oauth_complete_signup'))
        self.assertEqual(response.status_code, 200)

    def test_login_get_while_authenticated_orphan_redirects(self):
        """GET /login/ as an orphan session sends the user to complete signup."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('oauth_complete_signup'))
