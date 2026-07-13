"""Marketing pages (About / Verified / Protection) are guest-only for buyers."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class BuyerHidesMarketingPagesTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username='buyer_mkt',
            email='buyer_mkt@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_guest_catalog_shows_marketing_nav_links(self):
        response = self.client.get('/catalogo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verified suppliers')
        self.assertContains(response, 'Order protection')
        self.assertContains(response, 'About TradeFlow')

    def test_buyer_tienda_hides_marketing_nav_links(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Verified suppliers')
        self.assertNotContains(response, 'Order protection')
        self.assertNotContains(response, 'About TradeFlow')
        self.assertNotContains(response, 'Acerca de TradeFlow Colón')
        self.assertNotContains(response, 'Protección del pedido')
        self.assertContains(response, 'My orders')

    def test_buyer_redirected_from_about(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/acerca/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/tienda/')

    def test_buyer_redirected_from_verified_suppliers(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/verified-suppliers/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/tienda/')

    def test_buyer_redirected_from_order_protection(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/order-protection/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/tienda/')

    def test_guest_can_open_marketing_pages(self):
        for path in ('/acerca/', '/verified-suppliers/', '/order-protection/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
