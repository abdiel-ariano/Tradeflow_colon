"""Buyer-facing product detail must not expose exact inventory counts."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Category, Company, Inventory, Product, UserProfile
from core.utils.product_availability import public_availability_label
from core.utils.product_pdp_content import parse_product_description_sections


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    LANGUAGE_CODE='en',
)
class ProductDetailBuyerPrivacyTests(TestCase):
    """Public PDP hides exact stock and structures real description data."""

    def setUp(self):
        self.company = Company.objects.create(
            name='PDP Supplier',
            is_verified=True,
            ruc='8-PDP-001',
        )
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Voltage Regulator Pack',
            description=(
                'Automatic voltage regulation, monitoring software. '
                'ZLC import. Master pack available.'
            ),
            sku='VR-PKG-01',
            unit_price=Decimal('199.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=1207, reserved_qty=0)
        self.buyer = User.objects.create_user(
            username='pdp_buyer',
            email='pdp_buyer@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)

    def test_public_pdp_hides_exact_inventory(self):
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')

        self.assertIn('In stock', body)
        self.assertIn('Availability', body)
        self.assertNotIn('In stock (', body)
        self.assertNotIn('Available stock', body)
        self.assertNotIn('1207 units', body)
        self.assertNotIn('>1207<', body)

    def test_buyer_pdp_structures_description_from_existing_text(self):
        self.client.force_login(self.buyer)
        response = self.client.get(f'/catalogo/producto/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')

        self.assertIn('Product overview', body)
        self.assertIn('Key features', body)
        self.assertIn('Automatic voltage regulation', body)
        self.assertIn('monitoring software', body)
        self.assertIn('ZLC import', body)
        self.assertIn('Master pack available', body)

    def test_public_card_signals_hide_exact_inventory(self):
        response = self.client.get('/catalogo/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('In stock', body)
        self.assertNotIn('1207', body)
        self.assertNotIn('units', body.lower())

    def test_cart_json_does_not_return_disponible(self):
        self.client.post(
            f'/carrito/agregar/{self.product.pk}/',
            {'cantidad': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        response = self.client.post(
            f'/carrito/actualizar/{self.product.pk}/',
            {'cantidad': 5000},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertNotIn('disponible', data.get('line', {}))
        self.assertNotIn('1207', data['message'])


class ProductAvailabilityUtilTests(TestCase):
  def test_qualitative_labels(self):
      self.assertEqual(public_availability_label(0), 'Out of stock')
      self.assertEqual(public_availability_label(3), 'Limited availability')
      self.assertEqual(public_availability_label(1207), 'In stock')


class ProductDescriptionParserTests(TestCase):
    def test_splits_sentences_into_features(self):
        sections = parse_product_description_sections(
            'Automatic voltage regulation, monitoring software. ZLC import. Master pack available.'
        )
        self.assertTrue(sections.has_content)
        self.assertEqual(len(sections.overview_paragraphs), 1)
        self.assertIn('Automatic voltage regulation', sections.overview_paragraphs[0])
        self.assertGreaterEqual(len(sections.feature_items), 2)
        joined = ' '.join(sections.feature_items)
        self.assertIn('Master pack available', joined)
