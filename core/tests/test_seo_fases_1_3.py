"""SEO Fases 1–3: slug PDP, proveedor pages, recursos hub, JSON-LD."""

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Product
from core.utils.seo import hreflang_alternates, organization_json_ld, product_json_ld


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEMO_CATALOG_DISCLOSURE=False,
    CSRF_COOKIE_SECURE=False,
)
class SeoSlugAndContentTests(TestCase):
    """Slug PDP, 301 from pk, supplier page, and content hub."""

    def setUp(self):
        self.company = Company.objects.create(name='ZLC Supplier Co', ruc='8-SEO-99')
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            name='Industrial LED Panel',
            sku='LED-1',
            company=self.company,
            category=self.category,
            unit_price=25,
            is_active=True,
        )
        self.company.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.product.slug)
        self.assertTrue(self.company.slug)

    def test_product_absolute_url_uses_slug(self):
        self.assertEqual(
            self.product.get_absolute_url(),
            reverse('catalogo_producto_detail', kwargs={'slug': self.product.slug}),
        )

    def test_pdp_slug_renders_json_ld(self):
        url = reverse('catalogo_producto_detail', kwargs={'slug': self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'application/ld+json')
        self.assertContains(response, '"@type":"Product"')
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'rel="alternate"')
        self.assertContains(response, 'hreflang="es"')

    def test_legacy_pk_redirects_to_slug(self):
        legacy = reverse('catalogo_producto_detail_pk', args=[self.product.pk])
        response = self.client.get(legacy)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response['Location'],
            reverse('catalogo_producto_detail', kwargs={'slug': self.product.slug}),
        )

    def test_proveedor_page(self):
        url = reverse('proveedor_detalle', kwargs={'slug': self.company.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.company.name)
        self.assertContains(response, self.product.name)

    def test_recursos_hub_and_guides(self):
        for name in (
            'recursos_hub',
            'recursos_guia_zlc',
            'recursos_guia_rfq',
            'recursos_guia_exportacion',
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, msg=name)

    def test_sitemap_uses_slugs_and_recursos(self):
        response = self.client.get('/sitemap.xml')
        body = response.content.decode('utf-8')
        self.assertIn(f'/catalogo/producto/{self.product.slug}/', body)
        self.assertIn(f'/proveedor/{self.company.slug}/', body)
        self.assertIn('/recursos/', body)
        self.assertIn('/recursos/zona-libre-colon/', body)

    def test_home_has_zlc_title_signal(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Colón Free Zone')
        self.assertContains(response, 'hreflang="en"')


class SeoJsonLdHelperTests(TestCase):
    def test_hreflang_and_org(self):
        alts = hreflang_alternates('/acerca/')
        langs = {a['hreflang'] for a in alts}
        self.assertEqual(langs, {'en', 'es', 'x-default'})
        org = organization_json_ld()
        self.assertEqual(org['@type'], 'Organization')
        self.assertIn('TradeFlow', org['name'])

    def test_product_json_ld_shape(self):
        company = Company.objects.create(name='JSON Co', ruc='1')
        product = Product.objects.create(
            name='Widget',
            company=company,
            unit_price=9.5,
            is_active=True,
        )
        data = product_json_ld(
            product,
            canonical='https://tradeflowcolon.com/catalogo/producto/widget/',
            image_url='https://tradeflowcolon.com/static/x.png',
        )
        self.assertEqual(data['@type'], 'Product')
        self.assertEqual(data['offers']['priceCurrency'], 'USD')
