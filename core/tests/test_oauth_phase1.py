"""OAuth phase 1 — Google / Outlook / LinkedIn signup helpers."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserApplication, UserProfile
from core.social_auth import (
    generate_username_from_email,
    resolve_oauth_provider,
    setup_profile_and_application,
)


@override_settings(
    DEBUG=True,
    SOCIAL_AUTH_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={
        'google': {'APP': {'client_id': 'test-google-id', 'secret': 'test-google-secret'}},
        'microsoft': {'APP': {'client_id': '', 'secret': ''}},
    },
)
class OAuthHelpersTests(TestCase):
    def test_resolve_oauth_provider_linkedin_alias(self):
        self.assertEqual(resolve_oauth_provider('linkedin'), 'linkedin_oauth2')
        self.assertEqual(resolve_oauth_provider('google'), 'google')

    def test_generate_username_from_email_unique(self):
        User.objects.create_user(username='john.doe', email='a@t.pa', password='x')
        name = generate_username_from_email('john.doe@example.com')
        self.assertNotEqual(name, 'john.doe')
        self.assertRegex(name, r'^[a-zA-Z][a-zA-Z0-9._]{2,29}$')

    def test_setup_profile_and_application(self):
        user = User.objects.create_user(username='oauthuser', email='o@t.pa', password='unused')
        setup_profile_and_application(user, 'seller')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'seller')
        app = UserApplication.objects.get(user=user)
        self.assertEqual(app.role, 'seller')

    def test_setup_profile_buyer_sets_onboarding_pending(self):
        user = User.objects.create_user(username='buyer_oauth', email='b@t.pa', password='unused')
        setup_profile_and_application(user, 'buyer')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'buyer')
        self.assertIsNone(profile.onboarding_completed_at)


@override_settings(
    DEBUG=True,
    EXPO_DEMO_MODE=True,
    SOCIAL_AUTH_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={
        'google': {'APP': {'client_id': 'test-google-id', 'secret': 'test-google-secret'}},
    },
)
class OAuthFlowViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_oauth_begin_signup_stores_role_in_session(self):
        url = reverse('oauth_begin_signup', kwargs={'provider': 'google'})
        resp = self.client.get(url + '?role=seller')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get('oauth_signup_role'), 'seller')
        self.assertTrue(resp['Location'].endswith('/accounts/google/login/'))

    def test_oauth_begin_signup_linkedin_resolves_provider(self):
        with self.settings(
            SOCIALACCOUNT_PROVIDERS={
                'google': {'APP': {'client_id': '', 'secret': ''}},
                'linkedin_oauth2': {
                    'APP': {'client_id': 'li-id', 'secret': 'li-secret'},
                },
            },
        ):
            url = reverse('oauth_begin_signup', kwargs={'provider': 'linkedin'})
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp['Location'].endswith('/accounts/linkedin_oauth2/login/'))

    def test_oauth_begin_signup_disabled_without_credentials(self):
        with self.settings(
            SOCIALACCOUNT_PROVIDERS={
                'google': {'APP': {'client_id': '', 'secret': ''}},
            },
        ):
            url = reverse('oauth_begin_signup', kwargs={'provider': 'google'})
            resp = self.client.get(url)
            self.assertRedirects(resp, reverse('signup'))

    def test_accounts_login_redirects_to_custom_login(self):
        resp = self.client.get('/accounts/login/')
        self.assertRedirects(resp, reverse('login'))

    def test_accounts_signup_redirects_to_custom_signup(self):
        resp = self.client.get('/accounts/signup/')
        self.assertRedirects(resp, reverse('signup'))

    def test_accounts_inactive_redirects_anonymous_to_login(self):
        resp = self.client.get('/accounts/inactive/')
        self.assertRedirects(resp, reverse('login'))

    def test_oauth_complete_signup_creates_profile(self):
        user = User.objects.create_user(
            username='newoauth',
            email='new@oauth.pa',
            password='unused',
        )
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        resp = self.client.post(
            reverse('oauth_complete_signup'),
            {'role': 'buyer'},
        )
        self.assertEqual(resp.status_code, 302)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'buyer')

    def test_oauth_post_signup_redirects_buyer_to_onboarding(self):
        user = User.objects.create_user(
            username='oauth_buyer',
            email='buyer@oauth.pa',
            password='unused',
        )
        user.set_unusable_password()
        user.is_active = True
        user.save()
        UserProfile.objects.create(
            user=user,
            role='buyer',
            email_verificado=True,
            onboarding_completed_at=None,
        )
        session = self.client.session
        session['oauth_signup_done'] = True
        session.save()
        self.client.force_login(user)
        resp = self.client.get(reverse('oauth_post_signup'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/onboarding/comprador', resp['Location'])

    def test_verificar_no_redirect_loop_without_profile(self):
        user = User.objects.create_user(
            username='loop_user',
            email='loop@test.pa',
            password='unused',
        )
        user.is_active = True
        user.save()
        self.client.force_login(user)
        resp = self.client.get('/verificar/', follow=True)
        self.assertLess(len(resp.redirect_chain), 4)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/signup/oauth/completar/', resp.redirect_chain[0][0])
