"""
=============================================================================
ACCIÓN: CREAR
DESTINO: core/merchandising.py
=============================================================================
Helpers de merchandising para home, tienda y API (ofertas, bestsellers, CMS).
=============================================================================
"""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import get_language

from .models import Category, Company, HomePromoSection, OrderItem, Product


def active_products_base():
    """QuerySet base de productos activos con relaciones."""
    return (
        Product.objects.filter(is_active=True)
        .select_related('company', 'category', 'inventory')
        .defer('company__owner')
    )


def daily_deals(limit: int = 8):
    """Productos con promoción vigente, prioridad merchandising."""
    now = timezone.now()
    return list(
        active_products_base()
        .filter(
            promo_price__isnull=False,
            promo_price__lt=models.F('unit_price'),
        )
        .filter(Q(promo_starts_at__isnull=True) | Q(promo_starts_at__lte=now))
        .filter(Q(promo_ends_at__isnull=True) | Q(promo_ends_at__gte=now))
        .order_by('-merchandising_priority', '-created_at')[:limit]
    )


def bestsellers(limit: int = 8, days: int = 30):
    """Top por unidades vendidas en ventana; fallback a flag is_bestseller."""
    since = timezone.now() - timedelta(days=days)
    top_ids = (
        OrderItem.objects.filter(order__created_at__gte=since)
        .exclude(order__status='cancelled')
        .values('product_id')
        .annotate(units=Sum('qty'))
        .order_by('-units')[:limit]
    )
    id_order = [row['product_id'] for row in top_ids if row['product_id']]
    if id_order:
        products = {p.pk: p for p in active_products_base().filter(pk__in=id_order)}
        ordered = [products[pk] for pk in id_order if pk in products]
        if len(ordered) >= max(1, limit // 2):
            return ordered[:limit]
    return list(
        active_products_base()
        .filter(Q(is_bestseller=True) | Q(is_featured=True))
        .order_by('-merchandising_priority', '-created_at')[:limit]
    )


def featured_products(limit: int = 8):
    """Destacados con fallback a productos activos recientes."""
    qs = (
        active_products_base()
        .filter(is_featured=True)
        .order_by('-merchandising_priority', '-created_at')[:limit]
    )
    if qs.exists():
        return list(qs)
    return list(
        active_products_base().order_by('-created_at')[:limit]
    )


def featured_companies_carousel(limit: int = 10):
    qs = (
        Company.objects.filter(is_featured=True)
        .annotate(num_productos=Count('products', filter=Q(products__is_active=True)))
        .filter(num_productos__gt=0)
        .order_by('-carousel_priority', 'name')[:limit]
    )
    if qs.exists():
        return list(qs)
    return list(
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('-num_productos')[:limit]
    )


def trending_products(limit: int = 8):
    """Trending row for public home — bestsellers with carousel fallback."""
    items = bestsellers(limit=limit)
    if len(items) >= 4:
        return items
    return carousel_products(limit=limit)


def home_company_tiers(premium_limit: int = 3, standard_limit: int = 5):
    """
    Split home companies into premium featured (with product carousel)
    and standard grid cards.
    """
    base_qs = (
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
    )
    premium_qs = list(
        base_qs.filter(is_featured=True)
        .order_by('-carousel_priority', '-num_productos', 'name')[:premium_limit]
    )
    premium_ids = {c.pk for c in premium_qs}
    if len(premium_qs) < premium_limit:
        for emp in base_qs.exclude(pk__in=premium_ids).order_by('-num_productos', 'name'):
            if len(premium_qs) >= premium_limit:
                break
            premium_qs.append(emp)
            premium_ids.add(emp.pk)

    product_map: dict[int, list] = {}
    if premium_qs:
        for product in (
            active_products_base()
            .filter(company_id__in=premium_ids)
            .order_by('company_id', '-merchandising_priority', '-created_at')
        ):
            bucket = product_map.setdefault(product.company_id, [])
            if len(bucket) < 5:
                bucket.append(product)

    premium = []
    for emp in premium_qs:
        emp.productos_destacados = product_map.get(emp.pk, [])
        premium.append(emp)

    standard = list(
        base_qs.exclude(pk__in=premium_ids).order_by('name')[:standard_limit]
    )
    return premium, standard


def carousel_products(limit: int = 12):
    """Productos para carrusel: promo, bestsellers o destacados."""
    deals = daily_deals(limit=limit)
    if len(deals) >= 4:
        return deals
    best = bestsellers(limit=limit)
    if len(best) >= 4:
        return best
    return list(
        active_products_base().order_by('-merchandising_priority', '-created_at')[:limit]
    )


def _section_in_window(section: HomePromoSection, now=None) -> bool:
    if now is None:
        now = timezone.now()
    if not section.is_active:
        return False
    if section.starts_at and now < section.starts_at:
        return False
    if section.ends_at and now > section.ends_at:
        return False
    return True


def active_home_sections(now=None):
    """Secciones CMS activas ordenadas."""
    if now is None:
        now = timezone.now()
    sections = HomePromoSection.objects.prefetch_related(
        'products', 'companies', 'categories'
    ).order_by('sort_order', 'slug')
    return [s for s in sections if _section_in_window(s, now)]


def resolve_section_products(section: HomePromoSection):
    """Productos para una sección según tipo y M2M."""
    limit = section.max_items or 8
    manual = list(
        section.products.filter(is_active=True).select_related(
            'company', 'category', 'inventory'
        )[:limit]
    )
    if manual:
        return manual
    st = section.section_type
    if st == 'daily_deals':
        return daily_deals(limit)
    if st == 'bestsellers':
        return bestsellers(limit)
    if st in ('product_row', 'product_carousel'):
        return featured_products(limit)
    if st == 'category_spotlight' and section.categories.exists():
        cat = section.categories.first()
        return list(
            active_products_base()
            .filter(category=cat)
            .order_by('-merchandising_priority')[:limit]
        )
    if st == 'company_spotlight' and section.companies.exists():
        comp = section.companies.first()
        return list(
            active_products_base()
            .filter(company=comp)
            .order_by('-merchandising_priority')[:limit]
        )
    return featured_products(limit)


def category_spotlights(limit_per_cat: int = 4, max_cats: int = 4):
    """Filas por categoría con productos activos."""
    rows = []
    for cat in Category.objects.annotate(
        n=Count('products', filter=Q(products__is_active=True))
    ).filter(n__gt=0).order_by('-n')[:max_cats]:
        prods = list(
            active_products_base()
            .filter(category=cat)
            .order_by('-merchandising_priority')[:limit_per_cat]
        )
        if prods:
            rows.append({'category': cat, 'products': prods})
    return rows


def home_stats():
    """Estadísticas para hero y home (datos reales ORM)."""
    from .models import Order

    since = timezone.now() - timedelta(days=30)
    gmv = (
        OrderItem.objects.filter(
            order__created_at__gte=since,
            order__status__in=('paid', 'packed', 'shipped', 'delivered'),
        ).aggregate(total=Sum('line_total'))['total']
        or 0
    )
    from .utils.money_format import format_money_usd, quantize_money

    gmv_dec = quantize_money(gmv)
    gmv_int = int(gmv_dec)

    empresas_verificadas = (
        Company.objects.filter(is_verified=True, products__is_active=True)
        .distinct()
        .count()
    )
    categorias_activas = (
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .count()
    )

    return {
        'empresas': empresas_verificadas or Company.objects.count(),
        'empresas_verificadas': empresas_verificadas,
        'productos': Product.objects.filter(is_active=True).count(),
        'ordenes': Order.objects.exclude(status='cancelled').count(),
        'ordenes_completadas': Order.objects.filter(status='delivered').count(),
        'categorias': categorias_activas or Category.objects.count(),
        'gmv_30d': gmv_int,
        'gmv_30d_fmt': format_money_usd(gmv_dec),
    }


def localized_company_tagline(company: Company) -> str:
    lang = (get_language() or 'es')[:2]
    if lang == 'en' and company.tagline_en:
        return company.tagline_en
    return company.tagline_es or ''
