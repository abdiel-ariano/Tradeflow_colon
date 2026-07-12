"""Legacy /tienda/ partial AJAX redirects to /catalogo/."""
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
        """Setup."""
        self.buyer = User.objects.create_user(
            username='buyer_ajax',
            email='buyer_ajax@test.pa',
            password='Test1234!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_tienda_partial_redirects_to_catalog(self):
        """Test tienda partial redirects to catalog."""
        self.client.force_login(self.buyer)
        response = self.client.get(
            '/tienda/',
            {'partial': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn('/catalogo/', response['Location'])
        self.assertIn('partial=1', response['Location'])

    def test_catalog_partial_returns_markup(self):
        """Test catalog partial returns markup."""
        self.client.force_login(self.buyer)
        response = self.client.get(
            '/catalogo/',
            {'partial': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="cat-results-root"', content)
        self.assertNotIn('<!DOCTYPE html>', content)
