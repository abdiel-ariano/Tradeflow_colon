"""Cart line images — product fallback pipeline, never raw session URLs."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Category, Company, Inventory, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class CartProductImageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ZLC Trading', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Sony Headphones',
            sku='SONY-1',
            unit_price=Decimal('99.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)
        self.buyer = User.objects.create_user(
            username='cart_buyer',
            email='cart@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_cart_uses_product_image_placeholder_not_session_url(self):
        """Stale session imagen URLs must not bypass the shared fallback img tag."""
        self.client.login(username='cart_buyer', password='TestPass123!')
        session = self.client.session
        session['carrito'] = {
            str(self.product.pk): {
                'nombre': self.product.name,
                'precio': str(self.product.unit_price),
                'cantidad': 1,
                'subtotal': str(self.product.unit_price),
                'imagen': 'https://broken.example.com/stale-product.jpg',
            }
        }
        session.save()

        response = self.client.get('/carrito/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-tf-product-image', html)
        self.assertIn('TFHomeMediaFallback', html)
        self.assertIn('data-hm-static', html)
        self.assertNotIn('broken.example.com/stale-product.jpg', html)
