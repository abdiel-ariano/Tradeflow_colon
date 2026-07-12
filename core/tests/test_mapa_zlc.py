"""Mapa CFZ: Leaflet + OpenStreetMap sin API key; acceso público."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Inventory, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class MapaZlcTests(TestCase):
    def setUp(self):
        """Setup."""
        from django.core.cache import cache

        cache.clear()

    def test_map_page_is_public_and_renders_leaflet(self):
        """Test map page is public and renders leaflet."""
        response = self.client.get(reverse('mapa_zlc'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tf-cfz-map')
        self.assertContains(response, 'tf-cfz-map-data')
        self.assertContains(response, 'leaflet')
        self.assertContains(response, 'tf-cfz-map.js')

    def test_map_payload_includes_company_markers(self):
        """Test map payload includes company markers."""
        company = Company.objects.create(
            name='Map Test Co',
            is_verified=True,
            latitud=9.37,
            longitud=-79.91,
        )
        cat = Category.objects.create(name='Map Cat')
        product = Product.objects.create(
            name='Map Product',
            sku='MAP-1',
            company=company,
            category=cat,
            unit_price='12.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=product, stock_qty=10, reserved_qty=0)

        response = self.client.get(reverse('mapa_zlc'))
        self.assertEqual(response.status_code, 200)
        payload = response.context['map_payload']
        self.assertIn('markers', payload)
        self.assertIn('center', payload)
        names = [m['name'] for m in payload['markers']]
        self.assertIn('Map Test Co', names)

    def test_navbar_has_map_icon_without_duplicate_quotes(self):
        """Test navbar has map icon without duplicate quotes."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('mapa_zlc'))
        # One document icon for quotes, not two chat+document duplicates.
        self.assertEqual(
            response.content.decode().count('bn-utility--icon'),
            2,
        )
