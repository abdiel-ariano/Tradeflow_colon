"""OAuth must enter the same B2B identity flow as password signup."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserApplication
from core.social_auth import setup_b2b_profile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SOCIAL_AUTH_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={
        'google': {
            'APP': {
                'client_id': 'test-google-id',
                'secret': 'test-google-secret',
            },
        },
    },
)
class OAuthB2BOnboardingTests(TestCase):
    """Assert company intent, privacy and removal of legacy applications."""

    def setUp(self):
        self.client = Client()

    def _oauth_user(self, username='oauth_company'):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.pa',
            password='unused',
        )
        user.set_unusable_password()
        user.save()
        return user

    def test_b2b_profile_both_uses_seller_bridge_without_legacy_application(self):
        """Dual-capability OAuth accounts continue to company verification."""
        user = self._oauth_user('oauth_both')

        setup_b2b_profile(user, 'both', privacy_accepted=True)

        profile = user.profile
        self.assertEqual(profile.role, 'seller')
        self.assertEqual(profile.business_role_intent, 'both')
        self.assertIsNotNone(profile.onboarding_completed_at)
        self.assertIsNotNone(profile.privacy_accepted_at)
        self.assertFalse(UserApplication.objects.filter(user=user).exists())

    def test_begin_signup_preserves_both_company_intent(self):
        """The provider round trip remembers all three B2B choices."""
        url = reverse('oauth_begin_signup', kwargs={'provider': 'google'})

        response = self.client.get(f'{url}?business_role=both')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.session.get('oauth_selected_business_role'),
            'both',
        )
        self.assertTrue(response['Location'].endswith('/accounts/google/login/'))

    def test_completion_requires_privacy_acceptance(self):
        """OAuth cannot bypass the legal acceptance in password signup."""
        user = self._oauth_user('oauth_no_terms')
        self.client.force_login(user)

        response = self.client.post(
            reverse('oauth_complete_signup'),
            {'business_role': 'buyer'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(hasattr(user, 'profile'))

    def test_completion_persists_company_intent_without_legacy_review(self):
        """A valid OAuth choice reaches OTP, then RUC/DV onboarding."""
        user = self._oauth_user('oauth_valid')
        self.client.force_login(user)

        response = self.client.post(
            reverse('oauth_complete_signup'),
            {'business_role': 'buyer', 'accept_privacy': '1'},
        )

        self.assertRedirects(response, reverse('oauth_post_signup'))
        user.refresh_from_db()
        self.assertEqual(user.profile.business_role_intent, 'buyer')
        self.assertEqual(user.profile.role, 'buyer')
        self.assertFalse(UserApplication.objects.filter(user=user).exists())

    def test_unified_signup_exposes_google_for_selected_business_role(self):
        """The B2B signup page keeps its social-auth entry point."""
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-oauth-signup')
        self.assertContains(response, 'name="business_role"', count=3)
        self.assertContains(response, 'business_role=')
