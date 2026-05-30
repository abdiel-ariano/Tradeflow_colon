"""Catálogo tienda: respuesta partial AJAX."""
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
class TiendaCatalogAjaxTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username='buyer_ajax',
            email='buyer_ajax@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_tienda_partial_returns_catalog_markup(self):
        self.client.force_login(self.buyer)
        response = self.client.get(
            '/tienda/',
            {'partial': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="td-product-grid"', content)
        self.assertIn('t-prod-section', content)
        self.assertNotIn('<!DOCTYPE html>', content)
