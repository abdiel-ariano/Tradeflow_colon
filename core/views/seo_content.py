"""SEO content surfaces: supplier storefronts and B2B resource guides (Fase 3)."""
from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from core.decorators import catalog_access
from core.models import Company, Product
from core.utils.seo import absolute_reverse, breadcrumb_json_ld, dumps_json_ld
from core.views.catalog_cart import _contar_items, _get_carrito


def _content_base_context(request):
    return {
        'carrito_count': _contar_items(_get_carrito(request)),
    }


@require_GET
@cache_control(public=True, max_age=600)
@catalog_access
def proveedor_detalle(request, slug):
    """Public supplier storefront — products from one CFZ company."""
    company = get_object_or_404(Company, slug=slug)
    products_qs = (
        Product.objects.filter(company=company, is_active=True)
        .select_related('company', 'category', 'inventory')
        .order_by('-merchandising_priority', '-is_featured', 'name')
    )
    paginator = Paginator(products_qs, 24)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    canonical = absolute_reverse('proveedor_detalle', kwargs={'slug': company.slug})
    meta_description = _(
        '%(company)s — wholesale supplier in the Colón Free Zone. '
        'Browse products and request quotes on TradeFlow Colón.'
    ) % {'company': company.name}
    crumbs = [
        (_('Home'), absolute_reverse('home')),
        (_('Verified suppliers'), absolute_reverse('marketplace_verified_suppliers')),
        (company.name, canonical),
    ]
    ctx = _content_base_context(request)
    ctx.update(
        {
            'company': company,
            'productos': page_obj,
            'total_productos': paginator.count,
            'meta_description': meta_description,
            'canonical_url': canonical,
            'page_title': _(
                '%(company)s — CFZ Wholesale Supplier | TradeFlow Colón'
            )
            % {'company': company.name},
            'seo_json_ld_breadcrumb': dumps_json_ld(breadcrumb_json_ld(crumbs)),
            'marketplace_nav_active': 'verified',
            'show_cart_actions': (
                not request.user.is_authenticated
                or getattr(getattr(request.user, 'profile', None), 'role', None)
                in ('buyer', 'admin')
                or request.user.is_superuser
            ),
        }
    )
    return render(request, 'core/proveedor_detalle.html', ctx)


@require_GET
@cache_control(public=True, max_age=3600)
def recursos_hub(request):
    """Content hub for CFZ / B2B wholesale guides."""
    guides = [
        {
            'url_name': 'recursos_guia_zlc',
            'title': _('Colón Free Zone wholesale guide'),
            'summary': _(
                'How the Zona Libre de Colón works for importers: verified suppliers, '
                'USD pricing, and export documentation.'
            ),
        },
        {
            'url_name': 'recursos_guia_rfq',
            'title': _('RFQ and MOQ on TradeFlow'),
            'summary': _(
                'Request formal quotes, compare MOQs, and negotiate before you commit '
                'to a wholesale order.'
            ),
        },
        {
            'url_name': 'recursos_guia_exportacion',
            'title': _('Export-ready documentation'),
            'summary': _(
                'Invoices, packing lists, and CFZ paperwork buyers expect when shipping '
                'from Panama.'
            ),
        },
    ]
    ctx = _content_base_context(request)
    ctx.update(
        {
            'guides': guides,
            'page_title': _('CFZ Wholesale Guides | TradeFlow Colón'),
            'meta_description': _(
                'Guides for buying wholesale from the Colón Free Zone: ZLC basics, '
                'RFQ/MOQ workflows, and export documentation on TradeFlow Colón.'
            ),
            'canonical_url': absolute_reverse('recursos_hub'),
            'marketplace_nav_active': 'about',
        }
    )
    return render(request, 'core/recursos_hub.html', ctx)


def _render_guide(request, *, template, title, meta_description, url_name):
    canonical = absolute_reverse(url_name)
    crumbs = [
        (_('Home'), absolute_reverse('home')),
        (_('Guides'), absolute_reverse('recursos_hub')),
        (title, canonical),
    ]
    ctx = _content_base_context(request)
    ctx.update(
        {
            'page_title': f'{title} | TradeFlow Colón',
            'meta_description': meta_description,
            'canonical_url': canonical,
            'seo_json_ld_breadcrumb': dumps_json_ld(breadcrumb_json_ld(crumbs)),
            'marketplace_nav_active': 'about',
            'guide_title': title,
        }
    )
    return render(request, template, ctx)


@require_GET
@cache_control(public=True, max_age=3600)
def recursos_guia_zlc(request):
    """Guide: buying wholesale from the Colón Free Zone."""
    return _render_guide(
        request,
        template='core/recursos_guia_zlc.html',
        title=_('Colón Free Zone wholesale guide'),
        meta_description=_(
            'Learn how wholesale trade works in the Colón Free Zone (Zona Libre de Colón) '
            'and how TradeFlow connects buyers with verified CFZ suppliers.'
        ),
        url_name='recursos_guia_zlc',
    )


@require_GET
@cache_control(public=True, max_age=3600)
def recursos_guia_rfq(request):
    """Guide: RFQ and MOQ workflows."""
    return _render_guide(
        request,
        template='core/recursos_guia_rfq.html',
        title=_('RFQ and MOQ on TradeFlow'),
        meta_description=_(
            'How to request quotes (RFQ), compare MOQs in USD, and negotiate wholesale '
            'orders with Colón Free Zone suppliers on TradeFlow.'
        ),
        url_name='recursos_guia_rfq',
    )


@require_GET
@cache_control(public=True, max_age=3600)
def recursos_guia_exportacion(request):
    """Guide: export documentation from CFZ."""
    return _render_guide(
        request,
        template='core/recursos_guia_exportacion.html',
        title=_('Export-ready documentation'),
        meta_description=_(
            'Export documents for Colón Free Zone wholesale: commercial invoice, packing '
            'list, and what buyers need when shipping from Panama via TradeFlow.'
        ),
        url_name='recursos_guia_exportacion',
    )
