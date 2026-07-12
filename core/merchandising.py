"""
=============================================================================
ACCIÓN: CREAR
DESTINO: core/merchandising.py
=============================================================================
Helpers de merchandising para home, tienda y API (ofertas, bestsellers, CMS).
=============================================================================
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.db import models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import get_language

from core.utils.category_display import category_display_name
from .models import Category, Company, HomePromoSection, OrderItem, Product


def _product_has_uploaded_image(product) -> bool:
    """True when the product has a stored upload (local file or remote storage path)."""
    from core.utils.media_storage import is_remote_media_storage, local_media_file_exists

    if not getattr(product, 'image', None) or not product.image.name:
        return False
    rel = product.image.name.replace('\\', '/')
    if local_media_file_exists(rel):
        return True
    return is_remote_media_storage()


def _product_image_fingerprint(product) -> str:
    """Visual key for deduping identical fallback photos in the same home row."""
    from core.utils.demo_product_images import (
        ai_placeholder_file_exists,
        ai_placeholder_static_path,
        category_icon_static_path,
    )

    if _product_has_uploaded_image(product):
        return f'upload:{product.image.name.replace(chr(92), "/")}'
    if ai_placeholder_file_exists(product):
        return f'ai:{ai_placeholder_static_path(product)}'
    return f'icon:{category_icon_static_path(product)}'


def _sort_products_by_image_priority(products: list) -> list:
    """Prefer products with real uploads before icon/AI fallbacks."""
    return sorted(
        products,
        key=lambda p: (
            0 if _product_has_uploaded_image(p) else 1,
            -(getattr(p, 'merchandising_priority', 0) or 0),
            -p.pk,
        ),
    )


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


def ensure_marketplace_promos(minimum: int = 6) -> int:
    """
    Guarantee at least ``minimum`` active promo SKUs for public deals surfaces.

    Idempotent: only assigns promos when the catalog has fewer active deals than
    ``minimum`` (demo / fresh DB self-heal without a separate management command).
    """
    from decimal import Decimal

    active = daily_deals(minimum)
    if len(active) >= minimum:
        return len(active)

    now = timezone.now()
    ends = now + timedelta(days=30)
    needed = minimum - len(active)
    existing_ids = {p.pk for p in active}
    candidates = list(
        active_products_base()
        .exclude(pk__in=existing_ids)
        .filter(
            Q(promo_price__isnull=True)
            | Q(promo_price__gte=models.F('unit_price'))
        )
        .order_by('-merchandising_priority', '-is_featured', '-created_at')[:needed]
    )
    for product in candidates:
        product.promo_price = (product.unit_price * Decimal('0.85')).quantize(Decimal('0.01'))
        product.promo_starts_at = now
        product.promo_ends_at = ends
        product.save(update_fields=['promo_price', 'promo_starts_at', 'promo_ends_at'])

    return len(daily_deals(minimum))


def deals_page_products(limit: int = 48):
    """Products for the public /deals/ page — promos first, catalog fallback."""
    ensure_marketplace_promos(min(6, limit))
    deals = daily_deals(limit)
    if len(deals) >= 3:
        return deals
    return list(
        active_products_base()
        .order_by('-merchandising_priority', '-is_bestseller', '-created_at')[:limit]
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
            return _sort_products_by_image_priority(ordered)[:limit]
    return _sort_products_by_image_priority(
        list(
            active_products_base()
            .filter(Q(is_bestseller=True) | Q(is_featured=True))
            .order_by('-merchandising_priority', '-created_at')[: max(limit * 3, limit)]
        )
    )[:limit]


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


def buyer_mega_menu_panels(limit_categories: int = 8, products_per: int = 6) -> list:
    """
    Paneles del mega menú comprador (navbar «Todas las categorías»).

    Cada panel incluye la categoría real de la BD y productos destacados
    como sub-enlaces — evita emojis hardcodeados y búsquedas ?buscar= vacías.
    """
    from core.utils.tradeflow_cache import cached_nav_categories

    categories = cached_nav_categories()[:limit_categories]
    panels = []
    for cat in categories:
        products = list(
            active_products_base()
            .filter(category=cat)
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-is_featured', '-created_at')[:products_per]
        )
        panels.append({'category': cat, 'products': products})
    return panels


def tienda_featured_supplier(company_id):
    """Proveedor destacado para resultados filtrados (?empresa=) — estilo Alibaba."""
    if not company_id:
        return None
    try:
        company = (
            Company.objects.annotate(
                num_productos=Count('products', filter=Q(products__is_active=True)),
            )
            .get(pk=int(company_id))
        )
    except (Company.DoesNotExist, ValueError, TypeError):
        return None
    if company.num_productos <= 0:
        return None
    spotlight_products_for_companies([company], limit_per=5)
    return company


def tienda_featured_category(category_id, limit: int = 5):
    """Categoría destacada para resultados filtrados (?categoria=)."""
    if not category_id:
        return None
    try:
        category = Category.objects.get(pk=int(category_id))
    except (Category.DoesNotExist, ValueError, TypeError):
        return None
    products = list(
        active_products_base()
        .filter(category=category)
        .select_related('company', 'category', 'inventory')
        .order_by('-merchandising_priority', '-is_featured', '-created_at')[:limit]
    )
    if not products:
        return None
    return {'category': category, 'products': products}


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


def category_spotlights(
    limit_per_cat: int = 4,
    max_cats: int = 4,
    exclude_ids: set[int] | None = None,
):
    """Category rows for home — products not already shown in earlier scroll sections."""
    seen = set(exclude_ids or [])
    rows = []
    for cat in Category.objects.annotate(
        n=Count('products', filter=Q(products__is_active=True))
    ).filter(n__gt=0).order_by('-n')[:max_cats]:
        prods = []
        row_fingerprints: set[str] = set()
        for product in _sort_products_by_image_priority(
            list(
                active_products_base()
                .filter(category=cat)
                .order_by('-merchandising_priority', '-created_at')
            )
        ):
            if product.pk in seen:
                continue
            fp = _product_image_fingerprint(product)
            if fp in row_fingerprints:
                continue
            prods.append(product)
            seen.add(product.pk)
            row_fingerprints.add(fp)
            if len(prods) >= limit_per_cat:
                break
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
        row_fingerprints: set[str] = set()
        for product in _sort_products_by_image_priority(
            list(
                active_products_base()
                .filter(category=cat)
                .order_by('-merchandising_priority', '-created_at')
            )
        ):
            if product.pk in seen:
                continue
            fp = _product_image_fingerprint(product)
            if fp in row_fingerprints:
                continue
            picked.append(product)
            seen.add(product.pk)
            row_fingerprints.add(fp)
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


def _pick_unique_products(
    candidates,
    seen: set[int],
    limit: int,
    *,
    diverse_images: bool = False,
) -> list:
    """Return up to ``limit`` products not already in ``seen``; mutates ``seen``."""
    if diverse_images:
        candidates = _sort_products_by_image_priority(list(candidates))

    picked: list = []
    row_fingerprints: set[str] = set()
    for product in candidates:
        pk = getattr(product, 'pk', None)
        if pk is None or pk in seen:
            continue
        if diverse_images:
            fp = _product_image_fingerprint(product)
            if fp in row_fingerprints:
                continue
            row_fingerprints.add(fp)
        picked.append(product)
        seen.add(pk)
        if len(picked) >= limit:
            break
    return picked


def diversify_visible_order(products: list, *, window: int = 4) -> list:
    """
  Reorder a catalog page so identical image fingerprints are not adjacent.

  Keeps all SKUs but breaks visual copy-paste patterns in the first screenful.
    """
    if len(products) <= 1:
        return products

    remaining = list(products)
    ordered: list = []
    recent: list[str] = []

    while remaining:
        pick_at = 0
        for idx, product in enumerate(remaining):
            fp = _product_image_fingerprint(product)
            if fp not in recent[-window:]:
                pick_at = idx
                break
        product = remaining.pop(pick_at)
        ordered.append(product)
        recent.append(_product_image_fingerprint(product))

    return ordered


def gateway_carousel_products(
    daily_deals_list,
    bestsellers_list,
    featured_list,
    *,
    limit: int = 6,
) -> list:
    """Hero ATF carousel — promos first, then bestsellers, then featured."""
    out: list = []
    seen: set[int] = set()
    for product in daily_deals_list:
        if product.pk in seen:
            continue
        out.append(product)
        seen.add(product.pk)
        if len(out) >= limit:
            return out
    for product in bestsellers_list:
        if product.pk in seen:
            continue
        out.append(product)
        seen.add(product.pk)
        if len(out) >= limit:
            return out
    for product in featured_list:
        if product.pk in seen:
            continue
        out.append(product)
        seen.add(product.pk)
        if len(out) >= limit:
            return out
    return out


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

    # Reserve bestsellers before featured fallback pollutes `seen` (recent SKUs overlap).
    bestsellers_list = _pick_unique_products(bestsellers(24), seen, 8, diverse_images=True)
    if len(bestsellers_list) < 4:
        bestsellers_list = _pick_unique_products(bestsellers(24), seen, 8, diverse_images=False)
    if not bestsellers_list:
        bestsellers_list = _pick_unique_products(
            active_products_base()
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-created_at'),
            seen,
            8,
            diverse_images=False,
        )
    for product in bestsellers_list:
        seen.add(product.pk)

    for product in featured_list:
        seen.add(product.pk)

    promo_sections = []
    cms_types: set[str] = set()
    for section in active_home_sections():
        cms_types.add(section.section_type)
        raw_products = resolve_section_products(section)
        limit = section.max_items or 8
        has_manual = section.products.exists()
        if has_manual:
            products = list(raw_products[:limit])
        else:
            products = _pick_unique_products(
                raw_products,
                seen,
                limit,
                diverse_images=True,
            )
        for product in products:
            seen.add(product.pk)
        promo_sections.append({
            'section': section,
            'products': products,
            'title': section.title_for_lang(lang),
            'subtitle': section.subtitle_for_lang(lang),
        })

    daily_deals_list = _pick_unique_products(daily_deals(16), seen, 8, diverse_images=True)
    show_daily_deals_strip = (
        'daily_deals' not in cms_types and len(daily_deals_list) >= 3
    )
    show_bestsellers_section = 'bestsellers' not in cms_types

    empresas_home = list(
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')[:8]
    )
    if not empresas_home:
        empresas_home = featured_companies_carousel(8)
    # Supplier spotlight products are per-company (not deduped against home scroll):
    # buyers expect to see that supplier's catalog even if a SKU appeared above.
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

    marketplace_trending_categories = list(
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n', 'name')[:8]
    )

    sidebar_categories = list(
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n', 'name')[:12]
    )

    category_spotlight_rows = category_spotlights(4, 8, exclude_ids=seen)
    home_quad_cards = category_spotlights(4, 4, exclude_ids=None)
    category_discover = _category_discover_items(
        marketplace_trending_categories,
        category_spotlight_rows,
    )

    bento_spotlight_items = _bento_spotlight_items(
        featured_list,
        marketplace_trending_categories,
        lang=lang,
    )
    category_modal_panels = _category_modal_panels(sidebar_categories)
    promo_banner = _first_promo_banner_block(promo_sections)
    catalog_breadth_list = catalog_breadth_products(24, exclude_ids=seen)
    home_quad_card_rows = _home_quad_card_rows(max_rows=4, cats_per_row=4, products_per_cat=4)
    home_card_sections = _home_card_section_rows(
        lang=lang,
        daily_deals=daily_deals_list,
        bestsellers=bestsellers_list,
        catalog_breadth=catalog_breadth_list,
        featured_list=featured_list,
        categories=marketplace_trending_categories,
        promo_sections=promo_sections,
        cms_types=cms_types,
    )
    home_figma_sections = _build_home_figma_sections(card_rows=home_card_sections)
    gateway_carousel_list = gateway_carousel_products(
        daily_deals_list,
        bestsellers_list,
        featured_list,
        limit=6,
    )

    return {
        'stats': home_stats_uncached(),
        'hero_collage_products': hero_collage,
        'daily_deals': daily_deals_list,
        'bestsellers': bestsellers_list,
        'featured_products': featured_list,
        'gateway_carousel_products': gateway_carousel_list,
        'trending_products': _pick_unique_products(
            trending_products(24), set(seen), 24, diverse_images=True,
        ),
        'texture_products': texture_products(12),
        'carousel_products': carousel_products(24),
        'catalog_breadth_products': catalog_breadth_list,
        'empresas_carousel': empresas_home,
        'empresas_premium': empresas_premium,
        'empresas_standard': empresas_standard,
        'category_spotlights': category_spotlight_rows,
        'home_quad_cards': home_quad_cards,
        'home_quad_card_rows': home_quad_card_rows,
        'home_card_sections': home_card_sections,
        'home_feed_carousels': home_card_sections,
        'home_figma_sections': home_figma_sections,
        'home_product_rows': _build_home_product_rows(
            featured_list=featured_list,
            daily_deals=daily_deals_list,
            bestsellers=bestsellers_list,
            catalog_breadth=catalog_breadth_list,
            promo_sections=promo_sections,
            show_daily_deals_strip=show_daily_deals_strip,
            show_bestsellers_section=show_bestsellers_section,
            lang=lang,
        ),
        'promo_sections': promo_sections,
        'show_daily_deals_strip': show_daily_deals_strip,
        'show_bestsellers_section': show_bestsellers_section,
        'marketplace_trending_categories': marketplace_trending_categories,
        'sidebar_categories': sidebar_categories,
        'category_discover': category_discover,
        'bento_spotlight_items': bento_spotlight_items,
        'category_modal_panels': category_modal_panels,
        'promo_banner': promo_banner,
    }


def marketplace_categories_context() -> dict:
    """Shared category rail + modal data for home and public catalog."""
    sidebar_categories = list(
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n', 'name')[:12]
    )
    trending = list(
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n', 'name')[:8]
    )
    spotlight_rows = category_spotlights(4, 8)
    return {
        'sidebar_categories': sidebar_categories,
        'category_discover': _category_discover_items(trending, spotlight_rows),
        'category_modal_panels': _category_modal_panels(sidebar_categories),
    }


def localized_company_tagline(company: Company) -> str:
    lang = (get_language() or 'es')[:2]
    if lang == 'en' and company.tagline_en:
        return company.tagline_en
    return company.tagline_es or ''


def _category_discover_items(trending_categories, spotlight_rows) -> list:
    """Circle tiles for home — category + representative product image."""
    by_cat = {row['category'].pk: row for row in spotlight_rows}
    items = []
    for cat in trending_categories:
        row = by_cat.get(cat.pk)
        product = row['products'][0] if row and row.get('products') else None
        items.append({'category': cat, 'product': product, 'badge': _category_discover_badge(cat.pk)})
    return items


def _category_discover_badge(category_pk: int) -> str:
    """Decorative trend badge — rotates by category pk."""
    if category_pk % 5 == 0:
        return 'hot'
    if category_pk % 3 == 0:
        return 'trend'
    return ''


def _bento_spotlight_items(featured_list, trending_categories, lang: str | None = None) -> list:
    """Two image-first tiles — category label + representative product."""
    items: list[dict] = []
    cats = list(trending_categories[:2])
    for i, cat in enumerate(cats):
        product = featured_list[i] if i < len(featured_list) else None
        if not product:
            product = (
                active_products_base()
                .filter(category=cat)
                .order_by('-merchandising_priority', '-created_at')
                .first()
            )
        if product:
            items.append({
                'category': cat,
                'product': product,
                'label': category_display_name(cat.name, lang=lang),
            })
    idx = len(items)
    while len(items) < 2 and idx < len(featured_list):
        product = featured_list[idx]
        items.append({
            'category': product.category,
            'product': product,
            'label': category_display_name(product.category.name, lang=lang) if product.category else 'Featured',
        })
        idx += 1
    return items[:2]


def _category_modal_panels(categories, products_per: int = 18) -> list:
    """Sidebar + grid data for Alibaba-style categories overlay."""
    panels = []
    for cat in categories:
        products = list(
            active_products_base()
            .filter(category=cat)
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-created_at')[:products_per]
        )
        panels.append({'category': cat, 'products': products})
    return panels


def _first_promo_banner_block(promo_sections) -> dict | None:
    for block in promo_sections:
        if block['section'].section_type == 'seasonal_banner':
            return block
    return None


def _build_home_product_rows(
    *,
    featured_list,
    daily_deals,
    bestsellers,
    catalog_breadth,
    promo_sections,
    show_daily_deals_strip,
    show_bestsellers_section,
    lang: str,
) -> list:
    """Thin horizontal product rows for unified Alibaba-style home."""
    rows: list[dict] = []
    cms_types: set[str] = {block['section'].section_type for block in promo_sections}

    def _row(slug, dom_id, title, products, see_all_query='', min_products=2):
        if len(products) < min_products:
            return
        rows.append({
            'slug': slug,
            'dom_id': dom_id,
            'title': title,
            'see_all_query': see_all_query,
            'products': list(products)[:12],
        })

    deals_title = 'Today\'s wholesale deals' if lang == 'en' else 'Ofertas del día'
    best_title = 'Recommended for your business' if lang == 'en' else 'Recomendado para tu negocio'
    for_you_title = 'Products for you' if lang == 'en' else 'Productos para ti'
    browse_title = 'More from the Free Zone' if lang == 'en' else 'Más de la Zona Libre'

    cms_deals_done = False
    cms_best_done = False
    for block in promo_sections:
        section = block['section']
        products = block.get('products') or []
        if section.section_type == 'seasonal_banner':
            continue
        if section.section_type == 'daily_deals' and products:
            _row(section.slug, f'hm-promo-{section.slug}', block.get('title') or deals_title, products, 'orden=promo')
            cms_deals_done = True
        elif section.section_type == 'bestsellers' and products:
            _row(section.slug, f'hm-promo-{section.slug}', block.get('title') or best_title, products, 'orden=novedades')
            cms_best_done = True
        elif products:
            _row(
                section.slug,
                f'hm-promo-{section.slug}',
                block.get('title') or section.title_for_lang(lang),
                products,
            )

    if not cms_deals_done and daily_deals and len(daily_deals) >= 3:
        _row('deals', 'hm-deals', deals_title, daily_deals, 'orden=promo')

    featured_row = list(featured_list[2:10]) if len(featured_list) > 2 else list(featured_list)
    _row('for-you', 'hm-row-for-you', for_you_title, featured_row)

    if not cms_best_done and bestsellers and len(bestsellers) >= 4:
        _row('recommended', 'hm-bestsellers', best_title, bestsellers, 'orden=novedades')

    _row('browse', 'hm-catalog-wall', browse_title, catalog_breadth)

    return rows


def _home_quad_card_rows(
    max_rows: int = 4,
    cats_per_row: int = 4,
    products_per_cat: int = 4,
) -> list[list[dict]]:
    """Figma gw-card-layout rows — each inner list has up to 4 quad cards."""
    flat = category_spotlights(max_rows * cats_per_row, products_per_cat, exclude_ids=None)
    rows: list[list[dict]] = []
    for i in range(0, len(flat), cats_per_row):
        chunk = flat[i:i + cats_per_row]
        if chunk:
            rows.append(chunk)
    return rows[:max_rows]


def _home_card_section_rows(
    *,
    lang: str,
    daily_deals,
    bestsellers,
    catalog_breadth,
    featured_list,
    categories,
    promo_sections,
    cms_types: set[str] | None = None,
) -> list[dict]:
    """Home main content — product card rows (not horizontal carousels)."""
    rows: list[dict] = []
    used_ids: set[int] = set()
    cms_types = cms_types or set()

    def _add(
        title: str,
        products,
        see_all_query: str = '',
        *,
        slug: str | None = None,
        preserve_order: bool = False,
        min_products: int = 4,
    ):
        if preserve_order:
            picked = list(products)[:8]
        else:
            picked = []
            for product in products:
                if product.pk in used_ids:
                    continue
                picked.append(product)
                used_ids.add(product.pk)
                if len(picked) >= 8:
                    break
        if len(picked) < min_products:
            return
        row_slug = slug or f'section-{len(rows)}'
        rows.append({
            'slug': row_slug,
            'dom_id': f'hm-row-{row_slug}',
            'title': title,
            'products': picked,
            'see_all_query': see_all_query,
        })
        if preserve_order:
            for product in picked:
                used_ids.add(product.pk)

    deals_title = 'Today\'s wholesale deals' if lang == 'en' else 'Ofertas del día'
    best_title = 'Recommended for your business' if lang == 'en' else 'Recomendado para tu negocio'
    browse_title = 'More from the Colón Free Zone' if lang == 'en' else 'Más de la Zona Libre de Colón'

    for block in promo_sections:
        section = block['section']
        products = block.get('products') or []
        if section.section_type == 'seasonal_banner' or len(products) < 4:
            continue
        _add(
            block.get('title') or section.title_for_lang(lang),
            products,
            preserve_order=True,
            slug=section.slug,
        )

    if 'daily_deals' not in cms_types and daily_deals:
        _add(deals_title, daily_deals, 'orden=promo', slug='deals')
    if 'bestsellers' not in cms_types and bestsellers:
        _add(best_title, bestsellers, 'orden=novedades', slug='bestsellers')

    for cat in categories[:4]:
        cat_products = list(
            active_products_base()
            .filter(category=cat)
            .order_by('-merchandising_priority', '-created_at')[:16]
        )
        if lang == 'en':
            title = f'Top wholesale in {cat.name}'
        else:
            title = f'Mayoristas en {cat.name}'
        _add(title, cat_products, f'categoria={cat.pk}', slug=f'cat-{cat.pk}')

    if catalog_breadth:
        _add(browse_title, catalog_breadth, slug='browse')

    featured_tail = list(featured_list[2:]) if len(featured_list) > 2 else list(featured_list)
    if featured_tail:
        for_you = 'Products for you' if lang == 'en' else 'Productos para ti'
        _add(for_you, featured_tail, slug='for-you')

    return rows[:6]


def _build_home_figma_sections(*, card_rows: list[dict]) -> list[dict]:
    """Main home scroll — stacked product card rows below hero."""
    return [{'type': 'cards', **row} for row in card_rows]


# =============================================================================
# Onboarding comprador — categorías y sugerencias Deep Search
# =============================================================================

def buyer_onboarding_category_choices(limit: int = 12) -> list[dict]:
    """
    Filas para el paso 2 del wizard — categorías con producto representativo.
    Ordenadas por volumen de SKUs activos (las más relevantes primero).
    """
    rows: list[dict] = []
    cats = (
        Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(n__gt=0)
        .order_by('-n')[:limit]
    )
    for cat in cats:
        product = (
            active_products_base()
            .filter(category=cat)
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-created_at')
            .first()
        )
        rows.append({'category': cat, 'product': product, 'product_count': cat.n})
    return rows


def buyer_deep_search_suggestions(profile, limit: int = 4, seed: int = 0) -> list[dict]:
    """
    Sugerencias paso 3 — productos/categorías según intereses del comprador.
    ``seed`` rota el orden al pulsar «Mezclar sugerencias».
    """
    from django.urls import reverse

    cats = list(profile.preferred_categories.all())
    if not cats:
        cats = list(
            Category.objects.annotate(
                n=Count('products', filter=Q(products__is_active=True)),
            )
            .filter(n__gt=0)
            .order_by('-n')[:limit]
        )

    if seed:
        rng = random.Random(seed)
        cats = list(cats)
        rng.shuffle(cats)

    suggestions: list[dict] = []
    for cat in cats:
        if len(suggestions) >= limit:
            break
        product = (
            active_products_base()
            .filter(category=cat)
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', '-created_at')
            .first()
        )
        if not product:
            continue
        suggestions.append({
            'category': cat,
            'product': product,
            'label': cat.name,
            'search_query': cat.name,
            'url': f"{reverse('catalogo_publico')}?categoria={cat.pk}",
        })
    return suggestions


def buyer_recommended_products(profile, limit: int = 20, diverse: int = 5) -> list:
    """
    Recomendaciones personalizadas para /tienda/ según categorías preferidas.
    Fallback a destacados globales si no hay preferencias.
    """
    cat_ids = list(profile.preferred_categories.values_list('pk', flat=True))
    if not cat_ids:
        return _pick_unique_products(featured_products(limit), set(), diverse, diverse_images=True)

    pool = list(
        active_products_base()
        .filter(category_id__in=cat_ids)
        .select_related('company', 'category', 'inventory')
        .order_by('-merchandising_priority', '-created_at')[:limit]
    )
    if len(pool) < diverse:
        extra = featured_products(limit)
        seen = {p.pk for p in pool}
        for p in extra:
            if p.pk not in seen:
                pool.append(p)
                seen.add(p.pk)
            if len(pool) >= limit:
                break
    return _pick_unique_products(pool, set(), diverse, diverse_images=True)
