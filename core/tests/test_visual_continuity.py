"""Visual continuity: marketplace chrome and auth redirects."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Company, UserProfile
from core.utils.seller_lifecycle import start_seller_trial


@override_settings(CSRF_COOKIE_SECURE=False, REQUIRE_EMAIL_VERIFICATION=False)
class VisualContinuityChromeTests(TestCase):
    """Guest cart uses Alibaba marketplace nav, not navy public shell."""

    def test_guest_cart_uses_marketplace_navbar(self):
        response = self.client.get(reverse('ver_carrito'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('tf-nav-alibaba', body)
        self.assertIn('id="cat-catalog-nav"', body)
        self.assertNotIn('id="hm-public-nav"', body)
        self.assertIn('cat-site-footer', body)

    def test_legacy_signup_redirects_to_buyer(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('signup_buyer'))

    def test_password_reset_done_uses_login_figma_shell(self):
        response = self.client.get(reverse('password_reset_done'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'login-page-wrap--figma')
        self.assertNotContains(response, 'sp-card')


@override_settings(
    CSRF_COOKIE_SECURE=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    AXES_ENABLED=False,
)
class SellerLegacyRedirectTests(TestCase):
    """Legacy seller URLs bounce into the current portal shell."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='vis_seller',
            email='vis@seller.pa',
            password='Demo1234!Demo',
        )
        UserProfile.objects.create(
            user=self.user,
            role='seller',
            email_verificado=True,
        )
        company = Company.objects.create(
            name='Vis Seller Co',
            ruc='8-VIS-1',
            owner=self.user,
        )
        start_seller_trial(company)
        self.client = Client()
        self.client.force_login(self.user)

    def test_legacy_panel_redirects_to_portal(self):
        response = self.client.get(reverse('seller_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('portal_seller'))
