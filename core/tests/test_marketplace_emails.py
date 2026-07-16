"""Marketplace lifecycle emails and cart activity snapshots.

Abandoned-cart and promo mail drive B2B reactivation; profile
cart counters feed reminder scheduling without extra queries.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='TradeFlow <no-reply@tradeflowcolon.com>',
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
)
class MarketplaceEmailTests(TestCase):
    """Assert welcome, abandoned-cart, and promo HTML templates."""

    def setUp(self):
        """Create verified buyer and a promo-priced CFZ product."""
        self.user = User.objects.create_user(
            username='buyer1',
            email='buyer1@example.com',
            password='pass12345',
            first_name='Ana',
        )
        UserProfile.objects.filter(user=self.user).update(
            role='buyer',
            email_verificado=True,
        )
        self.company = Company.objects.create(
            name='CFZ Demo Co',
            is_verified=True,
            tagline_es='Export-ready textiles',
        )
        self.category = Category.objects.create(name='Textiles')
        Product.objects.create(
            name='Camisa polo mayorista',
            sku='POLO-001',
            company=self.company,
            category=self.category,
            unit_price=Decimal('12.50'),
            promo_price=Decimal('9.99'),
            is_active=True,
        )

    @patch('core.utils.email_sender.send_mail', return_value=True)
    def test_enviar_bienvenida_uses_marketplace_template(self, mock_send):
        """Welcome email includes catalog CTA and Spanish greeting."""
        from core.utils.email_sender import enviar_bienvenida

        enviar_bienvenida(self.user)
        mock_send.assert_called_once()
        html = mock_send.call_args.kwargs.get('html_message') or mock_send.call_args[1].get('html_message', '')
        self.assertIn('¡Bienvenido', html)
        self.assertIn('Catálogo verificado', html)
        self.assertIn('Explorar catálogo', html)

    @patch('core.utils.email_sender.send_mail', return_value=True)
    def test_enviar_carrito_abandonado(self, mock_send):
        """Abandoned-cart email lists line items and return CTA."""
        from core.utils.email_sender import enviar_carrito_abandonado

        carrito = {
            '1': {
                'nombre': 'Camisa polo',
                'cantidad': 2,
                'subtotal': '25.00',
            },
        }
        ok = enviar_carrito_abandonado(self.user, carrito)
        self.assertTrue(ok)
        html = mock_send.call_args.kwargs.get('html_message') or ''
        self.assertIn('Se te olvidó algo', html)
        self.assertIn('Camisa polo', html)
        self.assertIn('Volver a mi carrito', html)

    @patch('core.utils.email_sender.send_mail', return_value=True)
    def test_enviar_promociones_empresas(self, mock_send):
        """Promo email highlights verified CFZ company names."""
        from core.utils.email_sender import enviar_promociones_empresas

        ok = enviar_promociones_empresas(self.user)
        self.assertTrue(ok)
        html = mock_send.call_args.kwargs.get('html_message') or ''
        self.assertIn('CFZ Demo Co', html)
        self.assertIn('Promociones', html)


class CartActivitySyncTests(TestCase):
    """Assert cart mutations update UserProfile activity fields."""

    def setUp(self):
        """Create buyer with stocked product for cart POSTs."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='cartbuyer',
            email='cart@example.com',
            password='pass12345',
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={'role': 'buyer', 'email_verificado': True},
        )
        self.company = Company.objects.create(name='Co')
        self.category = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            name='Widget',
            sku='W-1',
            company=self.company,
            category=self.category,
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=50, reserved_qty=0)

    def test_add_to_cart_updates_profile_activity(self):
        """Increment cart_items_count and stamp last activity."""
        self.client.force_login(self.user)
        url = reverse('agregar_al_carrito', kwargs={'producto_id': self.product.pk})
        self.client.post(url, {'cantidad': 3})
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.cart_items_count, 3)
        self.assertIsNotNone(profile.cart_last_activity_at)
        self.assertIsNone(profile.cart_reminder_sent_at)

    def test_empty_cart_clears_profile_snapshot(self):
        """Clear activity fields when the last cart item is removed."""
        self.client.force_login(self.user)
        add_url = reverse('agregar_al_carrito', kwargs={'producto_id': self.product.pk})
        self.client.post(add_url, {'cantidad': 1})
        remove_url = reverse('quitar_del_carrito', kwargs={'producto_id': self.product.pk})
        self.client.post(remove_url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.cart_items_count, 0)
        self.assertIsNone(profile.cart_last_activity_at)


class HomeNavbarTests(TestCase):
    """Assert home nav differs for guests vs authenticated buyers."""

    def setUp(self):
        """Create a verified buyer for logged-in nav checks."""
        self.buyer = User.objects.create_user(
            username='loggedbuyer',
            email='logged@example.com',
            password='pass12345',
        )
        UserProfile.objects.filter(user=self.buyer).update(role='buyer', email_verificado=True)

    def test_home_hides_duplicate_marketplace_nav_when_authenticated(self):
        """Hide guest catalog nav when buyer shell is active."""
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('bn-buyer-shell', html)
        self.assertNotIn('id="cat-catalog-nav"', html)

    def test_home_shows_marketplace_nav_for_guests(self):
        """Show catalog nav and auth CTAs for anonymous visitors."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="cat-catalog-nav"')
        self.assertContains(response, 'Sign in')
        self.assertContains(response, 'Create account')
        self.assertContains(response, 'bn-utility--signin')
        self.assertContains(response, 'hm-welcome-bar__auth')
