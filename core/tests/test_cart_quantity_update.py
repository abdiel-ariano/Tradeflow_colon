"""Cart quantity controls: AJAX updates, minus/plus, validation, persistence."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Inventory, Product, UserProfile


AJAX_HEADERS = {
    'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest',
    'HTTP_ACCEPT': 'application/json',
}


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '*'],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
)
class CartQuantityUpdateTests(TestCase):
    """Session cart quantity endpoint and cart page contract."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Cart Supplier',
            verification_status='verified',
        )
        self.category = Category.objects.create(name='Industrial')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Steel Widget',
            sku='SW-001',
            unit_price=Decimal('25.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)

        self.product_b = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Copper Bolt',
            sku='CB-002',
            unit_price=Decimal('5.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product_b, stock_qty=20, reserved_qty=0)

        self.buyer = User.objects.create_user(
            username='cart_buyer',
            email='cart@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

        self.guest = Client()
        self.auth = Client()
        self.auth.login(username='cart_buyer', password='TestPass123!')

    def _add_product(self, client, product, qty=1):
        return client.post(
            reverse('agregar_al_carrito', kwargs={'producto_id': product.pk}),
            {'cantidad': qty},
            **AJAX_HEADERS,
        )

    def _update_qty(self, client, product, qty):
        return client.post(
            reverse('actualizar_cantidad_carrito', kwargs={'producto_id': product.pk}),
            {'cantidad': qty},
            **AJAX_HEADERS,
        )

    def test_cart_page_renders_ajax_qty_controls(self):
        self._add_product(self.guest, self.product, 2)
        response = self.guest.get(reverse('ver_carrito'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('data-cart-qty-form', body)
        self.assertIn('data-cart-qty-decrease', body)
        self.assertIn('cart-item__info', body)
        self.assertIn('cart-item__toolbar', body)
        self.assertIn('data-cart-qty-increase', body)
        self.assertIn('data-cart-line-subtotal', body)
        self.assertIn('data-cart-summary-subtotal', body)
        self.assertNotIn('name="cantidad" value="{{ entry.item.cantidad|add', body)

    def test_decrease_quantity_via_ajax(self):
        self._add_product(self.guest, self.product, 3)
        response = self._update_qty(self.guest, self.product, 2)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['line']['cantidad'], 2)
        self.assertEqual(data['line']['subtotal'], '50.00')
        self.assertEqual(data['carrito_count'], 2)
        self.assertEqual(data['subtotal'], '50.00')
        self.assertEqual(self.guest.session['carrito'][str(self.product.pk)]['cantidad'], 2)

    def test_increase_quantity_sequence(self):
        self._add_product(self.guest, self.product, 1)
        for qty in (2, 3, 2, 1):
            response = self._update_qty(self.guest, self.product, qty)
            self.assertEqual(response.status_code, 200, response.content)
            data = response.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['line']['cantidad'], qty)
        self.assertEqual(self.guest.session['carrito'][str(self.product.pk)]['cantidad'], 1)

    def test_minus_at_minimum_rejected(self):
        self._add_product(self.guest, self.product, 1)
        response = self._update_qty(self.guest, self.product, 0)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn('removed', data)
        self.assertNotIn(str(self.product.pk), self.guest.session['carrito'])

    def test_exceeds_stock_rejected_with_current_line(self):
        self._add_product(self.guest, self.product, 2)
        response = self._update_qty(self.guest, self.product, 99)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['line']['cantidad'], 2)
        self.assertEqual(self.guest.session['carrito'][str(self.product.pk)]['cantidad'], 2)

    def test_invalid_quantity_rejected(self):
        self._add_product(self.guest, self.product, 2)
        response = self.guest.post(
            reverse('actualizar_cantidad_carrito', kwargs={'producto_id': self.product.pk}),
            {'cantidad': 'abc'},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn('removed', data)

    def test_persists_after_manual_reload(self):
        self._add_product(self.auth, self.product, 1)
        self._update_qty(self.auth, self.product, 4)
        response = self.auth.get(reverse('ver_carrito'))
        self.assertContains(response, 'value="4"', html=False)
        self.assertEqual(self.auth.session['carrito'][str(self.product.pk)]['cantidad'], 4)

    def test_authenticated_buyer_update(self):
        self._add_product(self.auth, self.product, 1)
        response = self._update_qty(self.auth, self.product, 5)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['carrito_count'], 5)

    def test_multiple_products_independent_updates(self):
        self._add_product(self.guest, self.product, 2)
        self._add_product(self.guest, self.product_b, 3)
        response_a = self._update_qty(self.guest, self.product, 4)
        response_b = self._update_qty(self.guest, self.product_b, 5)
        self.assertTrue(response_a.json()['ok'])
        self.assertTrue(response_b.json()['ok'])
        self.assertEqual(self.guest.session['carrito'][str(self.product.pk)]['cantidad'], 4)
        self.assertEqual(self.guest.session['carrito'][str(self.product_b.pk)]['cantidad'], 5)
        self.assertEqual(response_b.json()['carrito_count'], 9)

    def test_remove_via_ajax(self):
        self._add_product(self.guest, self.product, 2)
        response = self.guest.post(
            reverse('quitar_del_carrito', kwargs={'producto_id': self.product.pk}),
            {},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['carrito_count'], 0)
        self.assertEqual(self.guest.session.get('carrito', {}), {})

    def test_non_ajax_still_redirects(self):
        self._add_product(self.guest, self.product, 2)
        response = self.guest.post(
            reverse('actualizar_cantidad_carrito', kwargs={'producto_id': self.product.pk}),
            {'cantidad': 3},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.guest.session['carrito'][str(self.product.pk)]['cantidad'], 3)

    def test_cart_css_has_qty_pending_state(self):
        from pathlib import Path

        css = Path('static/css/carrito.css').read_text(encoding='utf-8')
        self.assertIn('.cart-qty--pending', css)
        self.assertIn('grid-template-areas', css)
        self.assertIn('.cart-page .cart-item', css)

    def test_carrito_js_uses_fetch_not_submit(self):
        from pathlib import Path

        js = Path('static/js/carrito_page.js').read_text(encoding='utf-8')
        self.assertIn('fetch(', js)
        self.assertIn('preventDefault', js)
        self.assertNotIn('form.submit()', js)
