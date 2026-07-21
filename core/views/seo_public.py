"""Public SEO endpoints: robots.txt and XML sitemap (Fases 0–3)."""
from __future__ import annotations

from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.utils.seo import (
    absolute_reverse,
    absolute_url,
    demo_catalog_blocks_indexing,
    robots_disallow_paths,
)


@require_GET
def robots_txt(request):
    """Serve robots.txt with disallow rules and sitemap pointer."""
    lines = [
        'User-agent: *',
        'Allow: /',
    ]
    for path in robots_disallow_paths():
        lines.append(f'Disallow: {path}')
    lines.append('')
    lines.append(f'Sitemap: {absolute_url("/sitemap.xml")}')
    lines.append('')
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')


def _url_entry(loc: str, *, lastmod=None, changefreq='weekly', priority='0.8') -> str:
    """One <url> block for the sitemap."""
    parts = ['  <url>', f'    <loc>{escape(loc)}</loc>']
    if lastmod is not None:
        if hasattr(lastmod, 'date'):
            lastmod = lastmod.date()
        parts.append(f'    <lastmod>{escape(str(lastmod))}</lastmod>')
    parts.append(f'    <changefreq>{escape(changefreq)}</changefreq>')
    parts.append(f'    <priority>{escape(priority)}</priority>')
    parts.append('  </url>')
    return '\n'.join(parts)


def _static_sitemap_urls() -> list[str]:
    """Marketing/legal/content URLs always listed."""
    names = (
        ('home', '1.0', 'daily'),
        ('acerca_tradeflow', '0.8', 'monthly'),
        ('marketplace_verified_suppliers', '0.7', 'weekly'),
        ('marketplace_deals', '0.6', 'weekly'),
        ('marketplace_order_protection', '0.5', 'monthly'),
        ('recursos_hub', '0.7', 'monthly'),
        ('recursos_guia_zlc', '0.6', 'monthly'),
        ('recursos_guia_rfq', '0.6', 'monthly'),
        ('recursos_guia_exportacion', '0.6', 'monthly'),
        ('legal_terminos', '0.3', 'yearly'),
        ('legal_privacidad', '0.3', 'yearly'),
        ('legal_cookies', '0.3', 'yearly'),
    )
    entries = []
    for name, priority, freq in names:
        entries.append(
            _url_entry(
                absolute_reverse(name),
                changefreq=freq,
                priority=priority,
            )
        )
    return entries


@require_GET
def sitemap_xml(request):
    """XML sitemap built from PUBLIC_BASE_URL (no Site framework dependency)."""
    entries = _static_sitemap_urls()

    if not demo_catalog_blocks_indexing():
        entries.append(
            _url_entry(
                absolute_reverse('catalogo_publico'),
                changefreq='daily',
                priority='0.9',
            )
        )
        from core.models import Company, Product

        products = (
            Product.objects.filter(is_active=True)
            .exclude(slug='')
            .order_by('-id')
            .only('id', 'slug', 'created_at')[:5000]
        )
        for product in products:
            lastmod = getattr(product, 'created_at', None) or timezone.now()
            entries.append(
                _url_entry(
                    absolute_reverse(
                        'catalogo_producto_detail', kwargs={'slug': product.slug}
                    ),
                    lastmod=lastmod,
                    changefreq='daily',
                    priority='0.7',
                )
            )

        companies = (
            Company.objects.exclude(slug='')
            .filter(products__is_active=True)
            .distinct()
            .order_by('name')
            .only('id', 'slug', 'created_at')[:2000]
        )
        for company in companies:
            lastmod = getattr(company, 'created_at', None) or timezone.now()
            entries.append(
                _url_entry(
                    absolute_reverse('proveedor_detalle', kwargs={'slug': company.slug}),
                    lastmod=lastmod,
                    changefreq='weekly',
                    priority='0.65',
                )
            )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(entries)
        + '\n</urlset>\n'
    )
    response = HttpResponse(body, content_type='application/xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=900'
    return response
