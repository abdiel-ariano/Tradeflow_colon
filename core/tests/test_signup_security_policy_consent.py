"""Signup security policy consent: modal markup and accept_privacy error copy."""
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class SignupSecurityPolicyConsentTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_buyer_renders_security_policy_modal(self):
        resp = self.client.get(reverse('signup_buyer'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('js-security-policy-open', content)
        self.assertIn('Security & Usage Policy — Summary', content)
        self.assertIn('signup-security-policy-modal', content)
        self.assertIn('name="accept_privacy"', content)
        self.assertIn('/privacidad/', content)
        self.assertIn('/terminos/', content)

    def test_signup_seller_renders_security_policy_modal(self):
        resp = self.client.get(reverse('signup_seller'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('js-security-policy-open', content)
        self.assertIn('Security & Usage Policy — Summary', content)
        self.assertIn('signup-security-policy-modal', content)

    def test_signup_buyer_rejects_without_accept_privacy(self):
        resp = self.client.post(
            reverse('signup_buyer'),
            {
                'first_name': 'Acme',
                'last_name': 'Corp',
                'username': 'acme_buyer_sp',
                'email': 'acme_buyer_sp@test.pa',
                'phone': '',
                'role': 'buyer',
                'password1': 'SecurePass1!',
                'password2': 'SecurePass1!',
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn(
            'must accept the Privacy Policy, Terms of use, and Security',
            content,
        )
        self.assertIn('Usage Policy to create an account', content)
