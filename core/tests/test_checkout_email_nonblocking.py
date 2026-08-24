"""Grouped RFQ creation from the inquiry cart.

The cart review must create one pending quote per verified supplier without
creating an order, payment, shipment, or inventory reservation.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Cotizacion,
    Inventory,
    Order,
    Payment,
    Product,
    UserProfile,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    AXES_ENABLED=False,
)
class GroupedCartRfqTests(TestCase):
    """Assert the inquiry cart becomes supplier-scoped formal RFQs."""

    def setUp(self):
        """Create a verified buyer and products from two verified suppliers."""
        self.buyer = User.objects.create_user(
            username='buyer_grouped_rfq',
            email='buyer@example.com',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.buyer,
            role='buyer',
            email_verificado=True,
        )
        category = Category.objects.create(name='Industrial')

        self.company_a = Company.objects.create(
            name='Atlantic ZLC',
            ruc='155600001',
            verification_status='verified',
        )
        self.company_b = Company.objects.create(
            name='Pacific ZLC',
            ruc='155600002',
            verification_status='verified',
        )
        self.product_a = Product.objects.create(
            company=self.company_a,
            category=category,
            name='Industrial Cable',
            sku='RFQ-A',
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        self.product_b = Product.objects.create(
            company=self.company_b,
            category=category,
            name='Safety Gloves',
            sku='RFQ-B',
            unit_price=Decimal('4.00'),
            is_active=True,
        )
        self.inventory_a = Inventory.objects.create(
            product=self.product_a,
            stock_qty=50,
            reserved_qty=0,
        )
        self.inventory_b = Inventory.objects.create(
            product=self.product_b,
            stock_qty=80,
            reserved_qty=0,
        )

        self.client.force_login(self.buyer)
        session = self.client.session
        session['carrito'] = {
            str(self.product_a.pk): {
                'nombre': self.product_a.name,
                'precio': str(self.product_a.unit_price),
                'cantidad': 3,
                'subtotal': '30.00',
                'imagen': '',
            },
            str(self.product_b.pk): {
                'nombre': self.product_b.name,
                'precio': str(self.product_b.unit_price),
                'cantidad': 5,
                'subtotal': '20.00',
                'imagen': '',
            },
        }
        session.save()

    def test_post_creates_one_pending_quote_per_supplier(self):
        """Posting the review creates grouped RFQs and clears the cart."""
        response = self.client.post(
            reverse('checkout'),
            {
                'notas': 'Quote FOB Colón and include export documents.',
                'validez_dias': '45',
            },
        )

        self.assertRedirects(response, reverse('mis_cotizaciones'))
        quotes = list(
            Cotizacion.objects.filter(buyer=self.buyer)
            .prefetch_related('items')
            .order_by('empresa_id')
        )
        self.assertEqual(len(quotes), 2)
        self.assertEqual(
            {quote.empresa_id for quote in quotes},
            {self.company_a.pk, self.company_b.pk},
        )
        self.assertEqual({quote.estado for quote in quotes}, {'pendiente'})
        self.assertEqual({quote.validez_dias for quote in quotes}, {45})
        self.assertEqual(len({quote.lote for quote in quotes}), 1)
        self.assertTrue(quotes[0].lote)
        self.assertEqual(sum(quote.items.count() for quote in quotes), 2)
        self.assertEqual(
            {item.cantidad_solicitada for quote in quotes for item in quote.items.all()},
            {3, 5},
        )

        self.assertFalse(Order.objects.filter(buyer=self.buyer).exists())
        self.assertFalse(Payment.objects.filter(order__buyer=self.buyer).exists())
        self.inventory_a.refresh_from_db()
        self.inventory_b.refresh_from_db()
        self.assertEqual(self.inventory_a.reserved_qty, 0)
        self.assertEqual(self.inventory_b.reserved_qty, 0)
        self.assertEqual(self.client.session.get('carrito'), {})
