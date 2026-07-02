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
            if len(bucket) < 16:
                bucket.append(product)

    premium = []
    for emp in premium_qs:
        emp.productos_destacados = product_map.get(emp.pk, [])
        premium.append(emp)

    standard = list(
        base_qs.exclude(pk__in=premium_ids).order_by('name')[:standard_limit]
    )
    return premium, standard


def spotlight_products_for_companies(companies, limit_per: int = 3):
    """
    Attach up to ``limit_per`` showcase products on each company for the home
    spotlight mini-carousel (ordered by merchandising priority).
    """
    if not companies:
        return
    company_ids = [c.pk for c in companies]
    product_map: dict[int, list] = {cid: [] for cid in company_ids}
    for product in (
        active_products_base()
        .filter(company_id__in=company_ids)
        .order_by('company_id', '-merchandising_priority', '-is_featured', '-created_at')
    ):
        bucket = product_map[product.company_id]
        if len(bucket) < limit_per:
            bucket.append(product)
    for emp in companies:
        emp.spotlight_products = product_map.get(emp.pk, [])


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


def active_home_section_types(now=None) -> set[str]:
    """Tipos de sección CMS activos en la landing (para evitar duplicados)."""
    return {section.section_type for section in active_home_sections(now)}


def has_active_home_section(section_type: str, now=None) -> bool:
    return section_type in active_home_section_types(now)


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
            rows.append({'category': cat, 'products': prods, 'product_count': cat.n})
    return rows


def texture_products(limit: int = 12):
    """Decorative product thumbnails for hero texture band."""
    items = carousel_products(limit=limit)
    if len(items) >= 8:
        return items
    return list(active_products_base().order_by('-merchandising_priority', '-created_at')[:limit])


def catalog_breadth_products(
    limit: int = 24,
    per_category: int = 2,
    max_categories: int = 12,
    exclude_ids: set[int] | None = None,
):
    """
    Diverse home sample across top categories — one wall of SKUs that
    reflects marketplace breadth instead of repeating the same few picks.
    """
    picked: list[Product] = []
    seen: set[int] = set(exclude_ids or [])

    cats = (
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n')[:max_categories]
    )

    for cat in cats:
        bucket = 0
        for product in (
            active_products_base()
            .filter(category=cat)
            .order_by('-merchandising_priority', '-created_at')
        ):
            if product.pk in seen:
                continue
            picked.append(product)
            seen.add(product.pk)
            bucket += 1
            if bucket >= per_category or len(picked) >= limit:
                break
        if len(picked) >= limit:
            break

    if len(picked) < limit:
        for product in active_products_base().order_by(
            '-merchandising_priority', '-created_at',
        ):
            if product.pk in seen:
                continue
            picked.append(product)
            seen.add(product.pk)
            if len(picked) >= limit:
                break

    return picked[:limit]


def home_stats_uncached():
    """Estadísticas para hero y home (datos reales ORM, sin cache)."""
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


def home_stats():
    """Estadísticas para hero y home — cacheadas en producción."""
    from core.utils.tradeflow_cache import cached_home_stats

    return cached_home_stats()


def _pick_unique_products(candidates, seen: set[int], limit: int) -> list:
    """Return up to ``limit`` products not already in ``seen``; mutates ``seen``."""
    picked: list = []
    for product in candidates:
        pk = getattr(product, 'pk', None)
        if pk is None or pk in seen:
            continue
        picked.append(product)
        seen.add(pk)
        if len(picked) >= limit:
            break
    return picked


def build_guest_home_context(lang: str) -> dict:
    """
    Contexto completo de la landing pública (invitados).
    Usado por home_view con cache por idioma.
    Product lists are deduplicated in scroll order so carousels do not repeat SKUs.
    """
    seen: set[int] = set()

    featured_qs = active_products_base().filter(is_featured=True).select_related(
        'company', 'category', 'inventory',
    ).order_by('-merchandising_priority', '-created_at')[:8]
    if not featured_qs.exists():
        featured_qs = active_products_base().select_related(
            'company', 'category', 'inventory',
        ).order_by('-created_at')[:8]
    featured_list = list(featured_qs)
    for product in featured_list:
        seen.add(product.pk)

    promo_sections = []
    cms_types: set[str] = set()
    for section in active_home_sections():
        cms_types.add(section.section_type)
        raw_products = resolve_section_products(section)
        limit = section.max_items or 8
        products = _pick_unique_products(raw_products, seen, limit)
        promo_sections.append({
            'section': section,
            'products': products,
            'title': section.title_for_lang(lang),
            'subtitle': section.subtitle_for_lang(lang),
        })

    daily_deals_list = _pick_unique_products(daily_deals(16), seen, 8)
    show_daily_deals_strip = (
        'daily_deals' not in cms_types and len(daily_deals_list) >= 3
    )
    show_bestsellers_section = 'bestsellers' not in cms_types

    bestsellers_list = _pick_unique_products(bestsellers(16), seen, 8)
    if not bestsellers_list:
        bestsellers_list = _pick_unique_products(
            active_products_base()
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-created_at'),
            seen,
            8,
        )

    empresas_home = list(
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')[:8]
    )
    if not empresas_home:
        empresas_home = featured_companies_carousel(8)
    spotlight_products_for_companies(empresas_home[:5], limit_per=3)

    empresas_premium, empresas_standard = home_company_tiers(3, 8)

    hero_collage = list(featured_list[:4])
    if len(hero_collage) < 3:
        for product in active_products_base().order_by('-merchandising_priority', '-created_at'):
            if product.pk in seen:
                continue
            hero_collage.append(product)
            if len(hero_collage) >= 4:
                break

    return {
        'stats': home_stats_uncached(),
        'hero_collage_products': hero_collage,
        'daily_deals': daily_deals_list,
        'bestsellers': bestsellers_list,
        'featured_products': featured_list,
        'trending_products': _pick_unique_products(
            trending_products(24), set(seen), 24,
        ),
        'texture_products': texture_products(12),
        'carousel_products': carousel_products(24),
        'catalog_breadth_products': catalog_breadth_products(24, exclude_ids=seen),
        'empresas_carousel': empresas_home,
        'empresas_premium': empresas_premium,
        'empresas_standard': empresas_standard,
        'category_spotlights': category_spotlights(4, 6),
        'promo_sections': promo_sections,
        'show_daily_deals_strip': show_daily_deals_strip,
        'show_bestsellers_section': show_bestsellers_section,
    }


def localized_company_tagline(company: Company) -> str:
    lang = (get_language() or 'es')[:2]
    if lang == 'en' and company.tagline_en:
        return company.tagline_en
    return company.tagline_es or ''
