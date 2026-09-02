"""Public CFZ map page with Leaflet markers for verified sellers.

Importers browse Colon Free Zone company locations without an
API key; navbar must expose the map without duplicate icons.
"""
from pathlib import Path

from django.conf import settings
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
    """Assert mapa_zlc payload, Leaflet assets, and nav."""

    def setUp(self):
        """Clear cache so map payload is rebuilt fresh."""
        from django.core.cache import cache

        cache.clear()

    def test_map_page_is_public_and_renders_leaflet(self):
        """Serve map page publicly with Leaflet container and script."""
        response = self.client.get(reverse('mapa_zlc'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tf-cfz-map')
        self.assertContains(response, 'tf-cfz-map-data')
        self.assertContains(response, 'map-zlc-layout')
        self.assertContains(response, 'tf-cfz-map-list')
        self.assertContains(response, 'leaflet')
        self.assertContains(response, 'tf-cfz-map.js')

    def test_map_payload_includes_company_markers(self):
        """Include verified companies with coordinates in map markers."""
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

    def test_map_script_does_not_move_page_when_selecting_marker(self):
        """Keep marker/list synchronization inside the sidebar and map."""
        script_path = Path(settings.BASE_DIR) / 'static/js/tf-cfz-map.js'
        source = script_path.read_text(encoding='utf-8')

        self.assertIn('function scrollListItemIntoView', source)
        self.assertNotIn('.scrollIntoView(', source)
        self.assertIn('autoPan: false', source)

    def test_navbar_has_map_icon_without_duplicate_quotes(self):
        """Link map from home nav without duplicate utility icons."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('mapa_zlc'))
        # One document icon for quotes, not two chat+document duplicates.
        self.assertEqual(
            response.content.decode().count('bn-utility--icon'),
            2,
        )
