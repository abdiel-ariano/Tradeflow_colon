"""Self-serve OAuth browse flow and soft email gates.

Buyers may browse and open cart before OTP; restricted actions
still force /verificar/ until email is confirmed.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import UserProfile
from core.social_auth import user_needs_oauth_role


@override_settings(
    DEBUG=True,
    SOCIAL_AUTH_ENABLED=True,
    REQUIRE_EMAIL_VERIFICATION=True,
    SOCIALACCOUNT_PROVIDERS={
        'google': {'APP': {'client_id': 'test-google-id', 'secret': 'test-google-secret'}},
    },
)
class OAuthSelfServeFlowTests(TestCase):
    """Assert activation, browse gates, and cart access."""

    def test_auto_activate_inactive_buyer_on_pre_login(self):
        """Activate eligible buyers and detect missing OAuth roles."""
        from core.social_auth import TradeFlowAccountAdapter, activate_user_if_eligible

        user = User.objects.create_user(username='react', email='r@t.pa', password='x')
        user.is_active = False
        user.save()
        UserProfile.objects.create(user=user, role='buyer', email_verificado=False)
        self.assertTrue(activate_user_if_eligible(user))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        adapter = TradeFlowAccountAdapter()
        fake_request = type('R', (), {'session': {}})()
        self.assertIsNone(
            adapter.pre_login(fake_request, user, email_verification='none', signup=False)
        )
        user = User.objects.create_user(username='oauth_new', email='new@g.pa', password='unused')
        user.set_unusable_password()
        user.save()
        self.assertTrue(user_needs_oauth_role(user))

    def test_browse_gate_only_for_missing_role(self):
        """Allow browse for unverified buyers; gate restricted scope."""
        from core.utils.access_gating import onboarding_redirect_name

        user = User.objects.create_user(username='browse_me', email='b@g.pa', password='x')
        user.is_active = True
        user.save()
        UserProfile.objects.create(user=user, role='buyer', email_verificado=False)
        self.assertIsNone(onboarding_redirect_name(user, scope='browse'))
        self.assertEqual(onboarding_redirect_name(user, scope='restricted'), 'verificar_codigo')

    def test_authenticated_unverified_can_open_cart(self):
        """Serve /carrito/ to authenticated unverified buyers."""
        user = User.objects.create_user(username='cart_guest', email='c@g.pa', password='x')
        user.is_active = True
        user.save()
        UserProfile.objects.create(user=user, role='buyer', email_verificado=False)
        client = Client()
        client.force_login(user)
        resp = client.get('/carrito/')
        self.assertEqual(resp.status_code, 200)
