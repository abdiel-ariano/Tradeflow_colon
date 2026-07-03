"""Catálogo público: invitados pueden explorar sin login."""
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
class GuestCatalogAccessTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.buyer = User.objects.create_user(
            username='buyer_guest_test',
            email='buyer_guest@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_guest_can_open_tienda(self):
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'td-product-grid', status_code=200)

    def test_guest_tienda_has_no_cart_actions(self):
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_cart_actions'])
        self.assertTrue(response.context['is_guest_catalog'])

    def test_guest_home_links_to_tienda_not_login_wall(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Browse catalog')
        self.assertNotContains(response, 'login/?next=/tienda/')

    def test_buyer_still_has_cart_actions(self):
        self.client.force_login(self.buyer)
        response = self.client.get('/tienda/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_cart_actions'])

    def test_guest_verificado_filter(self):
        response = self.client.get('/tienda/', {'verificado': '1'})
        self.assertEqual(response.status_code, 200)
