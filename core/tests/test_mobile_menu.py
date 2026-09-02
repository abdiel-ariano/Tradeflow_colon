"""Pruebas del menú compacto móvil (Android / PWA)."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile

User = get_user_model()


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver'],
)
class MobileMenuMarkupTests(TestCase):
    """Valida marcado y activos del menú hamburguesa por rol."""

    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(
            username='menu_test_buyer',
            password='Test1234!',
            email='menu-buyer@test.local',
        )
        UserProfile.objects.create(
            user=cls.buyer,
            role='buyer',
            email_verificado=True,
        )

    def setUp(self):
        self.client = Client()

    def test_guest_home_uses_public_hamburger_menu(self):
        """Invitado en home expone el menú público compacto."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cat-nav-hamburger"')
        self.assertContains(response, 'id="cat-nav-secondary"')
        self.assertContains(response, 'tf-mobile-pwa.js')

    def test_guest_catalog_does_not_hijack_hamburger_for_filters(self):
        """El catálogo no reasigna el hamburger al sidebar de filtros."""
        response = self.client.get(reverse('catalogo_publico'))
        js_path = settings.BASE_DIR / 'static' / 'js' / 'catalogo-publico.js'
        catalog_js = js_path.read_text(encoding='utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cat-nav-hamburger"')
        self.assertNotIn('navHamburger', catalog_js)

    def test_buyer_home_uses_buyer_shell_menu(self):
        """Comprador autenticado usa el toggle del buyer shell."""
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bn-mobile-toggle"')
        self.assertContains(response, 'id="bn-l2"')
        self.assertNotContains(response, 'id="cat-nav-hamburger"')

    def test_buyer_catalog_uses_buyer_shell_menu(self):
        """Comprador en catálogo conserva el menú buyer (no el público)."""
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('catalogo_publico'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bn-mobile-toggle"')
        self.assertContains(response, 'id="bn-l2"')

    def test_pwa_script_initializes_both_menu_shells(self):
        """El script móvil referencia ambos shells de navegación."""
        js_path = settings.BASE_DIR / 'static' / 'js' / 'tf-mobile-pwa.js'
        script = js_path.read_text(encoding='utf-8')

        self.assertIn('cat-catalog-nav', script)
        self.assertIn('bn-buyer-shell', script)
        self.assertIn('bn-mobile-toggle', script)
        self.assertIn('tf-market-menu-open', script)

    def test_mobile_css_requires_body_class_for_open_menu(self):
        """El panel secundario solo se muestra con clase en body."""
        css_path = settings.BASE_DIR / 'static' / 'css' / 'tf-mobile-pwa.css'
        css = css_path.read_text(encoding='utf-8')

        self.assertIn('body.tf-market-menu-open', css)
        self.assertIn('position: fixed', css)
