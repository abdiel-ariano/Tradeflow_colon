"""
TradeFlow AI Search — backend suggestion engine.

Architecture
------------
1. ``search_*`` functions query the ORM for the given scope (public, buyer, seller, admin).
2. ``build_search_response`` assembles the JSON payload consumed by ``/api/search/suggest/``.
3. Optional Groq enrichment adds a contextual tip and related phrases when ``GROQ_API_KEY`` is set.

Client integration
------------------
Any ``<input>`` with ``data-tf-ai-search="<scope>"`` is wired by ``static/js/tf-ai-search.js``.
See ``docs/AI_SEARCH.md`` for the full stack diagram and extension guide.

Scopes
------
- ``public``  — marketplace catalog (guest + anyone)
- ``buyer``   — authenticated buyer; empty query may return personalized picks
- ``seller``  — seller workspace (orders, products, customers, quotes)
- ``admin``   — staff product/company lookup
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse

log = logging.getLogger('tradeflow.ai_search')

# Tokens discarded when splitting multi-word queries (Spanish + English UX copy).
_STOPWORDS = frozenset({
    'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'y', 'o', 'a',
    'the', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'buscar', 'search',
    'quiero', 'need', 'find', 'show', 'me', 'my', 'product', 'producto',
})


def _tokens(q: str) -> list[str]:
    """Split a query into meaningful lowercase tokens (min length 2, no stopwords)."""
    raw = re.findall(r'[\wáéíóúüñ]+', (q or '').lower(), flags=re.UNICODE)
    return [t for t in raw if len(t) >= 2 and t not in _STOPWORDS]


def _item(
    kind: str,
    label: str,
    url: str,
    *,
    subtitle: str = '',
    icon: str = 'search',
    score: int = 0,
    image_url: str = '',
    meta: dict | None = None,
) -> dict:
    """
    Build one suggestion row for the typeahead JSON payload.

    ``image_url`` and ``meta`` are used by the client for rich product cards;
    other item types rely on ``icon`` + ``subtitle`` only.
    """
    row = {
        'type': kind,
        'label': label,
        'subtitle': subtitle,
        'url': url,
        'icon': icon,
        'score': score,
    }
    if image_url:
        row['image_url'] = image_url
    if meta:
        row['meta'] = meta
    return row


def _product_meta(product) -> dict:
    """Structured fields for the typeahead product card (company, SKU, price, etc.)."""
    price = getattr(product, 'display_price', None) or getattr(product, 'unit_price', None)
    return {
        'sku': (getattr(product, 'sku', None) or '').strip(),
        'company': product.company.name if getattr(product, 'company_id', None) else '',
        'category': product.category.name if getattr(product, 'category_id', None) else '',
        'price': str(price) if price is not None else '',
        'currency': getattr(product, 'currency', None) or 'USD',
    }


def _product_image_url(product) -> str:
    """Resolve the same image chain as catalog cards (upload → AI placeholder → seed icon)."""
    from core.templatetags.tf_media import product_image_src

    return product_image_src(product) or ''


def _product_item(product, url: str, *, score: int = 0, icon: str = 'inventory_2') -> dict:
    """Product suggestion with thumbnail + structured meta for the typeahead UI."""
    return _item(
        'product',
        product.name,
        url,
        subtitle=_product_subtitle(product),
        icon=icon,
        score=score,
        image_url=_product_image_url(product),
        meta=_product_meta(product),
    )


def _product_subtitle(product) -> str:
    """Legacy single-line subtitle (kept for non-JS consumers and seller/admin scopes)."""
    parts = []
    if getattr(product, 'sku', None):
        parts.append(product.sku)
    if getattr(product, 'company', None):
        parts.append(product.company.name)
    if getattr(product, 'category', None) and product.category:
        parts.append(product.category.name)
    price = getattr(product, 'display_price', None) or getattr(product, 'unit_price', None)
    if price is not None:
        cur = getattr(product, 'currency', 'USD') or 'USD'
        parts.append(f'{cur} {price}')
    return ' · '.join(parts[:4])


def _groq_search_enrichment(query: str, local_labels: list[str], scope: str) -> dict:
    """
    Optional LLM enrichment: one tip sentence + up to 4 related search phrases.

    Fails open (returns ``{}``) when Groq is unavailable or the API errors.
    """
    api_key = (getattr(settings, 'GROQ_API_KEY', None) or '').strip()
    if not api_key or len(query.strip()) < 2:
        return {}

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
        prompt = (
            f'User search on TradeFlow ({scope}): "{query[:120]}". '
            f'Local matches: {", ".join(local_labels[:8]) or "none"}. '
            'Reply JSON only with keys: tip (one short helpful sentence), '
            'related (array of 3 short related search phrases).'
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': 'You help B2B marketplace users search. JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=180,
            temperature=0.3,
        )
        text = (response.choices[0].message.content or '').strip()
        import json

        if '{' in text:
            text = text[text.index('{'): text.rindex('}') + 1]
            data = json.loads(text)
            return {
                'tip': str(data.get('tip', ''))[:220],
                'related': [str(x)[:60] for x in (data.get('related') or [])[:4]],
            }
    except Exception as exc:
        log.debug('groq search enrichment failed: %s', exc)
    return {}


def search_public(query: str, limit: int = 8) -> list[dict]:
    """
    Marketplace catalog suggestions.

    Empty query → featured products + top categories (trending).
    Non-empty → tokenized product name/SKU/description match, then categories and companies.
    """
    from .. import merchandising as merch
    from ..models import Category, Company

    q = (query or '').strip()
    if not q:
        trending = []
        for p in merch.featured_products(4):
            trending.append(_product_item(
                p,
                f"{reverse('catalogo_publico')}?buscar={p.name[:50]}",
                score=10,
            ))
        for cat in Category.objects.annotate(
            n=Count('products', filter=Q(products__is_active=True)),
        ).filter(n__gt=0).order_by('-n')[:3]:
            trending.append(_item(
                'category',
                cat.name,
                f"{reverse('catalogo_publico')}?categoria={cat.pk}",
                subtitle=f'{cat.n} products',
                icon='category',
                score=5,
            ))
        return trending[:limit]

    tokens = _tokens(q)
    product_q = Q()
    for t in tokens or [q.lower()]:
        product_q |= Q(name__icontains=t) | Q(sku__icontains=t) | Q(description__icontains=t)

    products = list(
        merch.active_products_base()
        .filter(product_q)
        .select_related('company', 'category', 'inventory')
        .order_by('-merchandising_priority', '-created_at')[:limit]
    )
    results = [
        _product_item(
            p,
            f"{reverse('catalogo_publico')}?buscar={p.name[:50]}",
            score=100 - i,
        )
        for i, p in enumerate(products)
    ]

    if len(results) < limit:
        cats = Category.objects.filter(name__icontains=q).order_by('name')[:3]
        for cat in cats:
            results.append(_item(
                'category',
                cat.name,
                f"{reverse('catalogo_publico')}?categoria={cat.pk}",
                subtitle='Category',
                icon='category',
                score=40,
            ))

    if len(results) < limit:
        companies = Company.objects.filter(
            is_verified=True,
            name__icontains=q,
        ).order_by('name')[:3]
        for co in companies:
            results.append(_item(
                'company',
                co.name,
                f"{reverse('catalogo_publico')}?empresa={co.pk}",
                subtitle='Verified seller',
                icon='storefront',
                score=35,
            ))

    if not results:
        results.append(_item(
            'action',
            f'Search catalog for "{q}"',
            f"{reverse('catalogo_publico')}?buscar={q}",
            subtitle='View all matching products',
            icon='search',
            score=1,
        ))
    return results[:limit]


def search_seller(company, query: str, limit: int = 10) -> list[dict]:
    """Seller workspace: products, orders, quotes, customers, or quick-action shortcuts."""
    from ..models import Cotizacion, Order, Product, User

    q = (query or '').strip()
    if not q:
        return [
            _item('action', 'Product catalog', reverse('seller_mis_productos'), icon='inventory_2', score=10),
            _item('action', 'Transactions', reverse('seller_mis_ventas'), icon='sync_alt', score=9),
            _item('action', 'Payments analytics', reverse('seller_reporting'), icon='monitoring', score=8),
            _item('action', 'Customers', reverse('seller_customers'), icon='group', score=7),
        ][:limit]

    results: list[dict] = []
    products = Product.objects.filter(company=company).filter(
        Q(name__icontains=q) | Q(sku__icontains=q) | Q(description__icontains=q)
    ).order_by('name')[:5]
    for p in products:
        results.append(_product_item(
            p,
            reverse('seller_editar_producto', args=[p.pk]),
            score=90,
        ))

    orders = (
        Order.objects.filter(items__product__company=company, order_number__icontains=q)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')[:4]
    )
    for o in orders:
        results.append(_item(
            'order',
            o.order_number,
            reverse('seller_detalle_venta', args=[o.pk]),
            subtitle=o.buyer.get_full_name() or o.buyer.username,
            icon='receipt_long',
            score=80,
        ))

    quotes = Cotizacion.objects.filter(empresa=company, numero__icontains=q).select_related('buyer')[:3]
    for cot in quotes:
        results.append(_item(
            'quote',
            cot.numero,
            reverse('seller_responder_cotizacion', args=[cot.pk]),
            subtitle=cot.buyer.username,
            icon='description',
            score=70,
        ))

    buyer_ids = list(
        Order.objects.filter(items__product__company=company)
        .values_list('buyer_id', flat=True)
        .distinct()
    )
    buyers = User.objects.filter(pk__in=buyer_ids).filter(
        Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
    )[:3]
    for u in buyers:
        results.append(_item(
            'customer',
            u.get_full_name() or u.username,
            f"{reverse('seller_customers')}?q={u.email or u.username}",
            subtitle=u.email,
            icon='person',
            score=60,
        ))

    if not results:
        results.append(_item(
            'action',
            f'Search "{q}" in workspace',
            f"{reverse('seller_global_search')}?q={q}",
            subtitle='Full search results',
            icon='search',
            score=1,
        ))
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]


def search_buyer(user, query: str, limit: int = 8) -> list[dict]:
    """
    Buyer navbar scope.

    Empty query + authenticated profile → personalized picks from merchandising.
    Otherwise delegates to ``search_public``.
    """
    from .. import merchandising as merch

    q = (query or '').strip()
    profile = getattr(user, 'profile', None) if user and user.is_authenticated else None

    if not q and profile:
        for row in merch.buyer_deep_search_suggestions(profile, limit=limit):
            p = row['product']
            return [
                _product_item(
                    p,
                    row['url'],
                    icon='auto_awesome',
                    score=50,
                )
            ]

    return search_public(q, limit=limit)


def search_admin(query: str, limit: int = 8) -> list[dict]:
    """Staff dashboard product/company lookup."""
    from ..models import Company, Product

    q = (query or '').strip()
    if not q:
        return [
            _item('action', 'Admin products', reverse('productos'), icon='inventory_2', score=10),
            _item('action', 'Dashboard', reverse('dashboard'), icon='dashboard', score=9),
        ][:limit]

    results = []
    for p in Product.objects.filter(
        Q(name__icontains=q) | Q(sku__icontains=q) | Q(description__icontains=q)
    ).select_related('company', 'category').order_by('-created_at')[:limit]:
        results.append(_product_item(
            p,
            f"{reverse('productos')}?buscar={q}",
            score=80,
        ))
    if len(results) < limit:
        for co in Company.objects.filter(name__icontains=q).order_by('name')[:3]:
            results.append(_item(
                'company',
                co.name,
                f"{reverse('productos')}?buscar={co.name}",
                subtitle='Company',
                icon='apartment',
                score=50,
            ))
    return results[:limit] or [
        _item('action', f'Search admin for "{q}"', f"{reverse('productos')}?buscar={q}", icon='search', score=1),
    ]


def build_search_response(scope: str, query: str, request, limit: int = 8) -> dict:
    """
    Assemble the JSON body for ``GET /api/search/suggest/``.

    Parameters
    ----------
    scope:
        One of ``public``, ``buyer``, ``seller``, ``admin``.
    query:
        Raw user input (trimmed server-side, max 120 chars).
    request:
        Django request — used for seller company resolution and buyer personalization.
    limit:
        Max suggestions (clamped 1–12 by the view).
    """
    q = (query or '').strip()[:120]
    suggestions: list[dict] = []

    if scope == 'seller':
        from ..models import Company

        company = None
        if request.user.is_authenticated:
            company = Company.objects.filter(owner=request.user).first()
        if not company:
            return {'ok': False, 'error': 'no_company', 'suggestions': [], 'query': q}
        suggestions = search_seller(company, q, limit=limit)
    elif scope == 'buyer':
        user = request.user if request.user.is_authenticated else None
        suggestions = search_buyer(user, q, limit=limit)
    elif scope == 'admin':
        suggestions = search_admin(q, limit=limit)
    else:
        suggestions = search_public(q, limit=limit)

    labels = [s['label'] for s in suggestions]
    enrichment = _groq_search_enrichment(q, labels, scope) if q else {}

    return {
        'ok': True,
        'query': q,
        'scope': scope,
        'suggestions': suggestions,
        'tip': enrichment.get('tip', ''),
        'related': enrichment.get('related', []),
        'ai_enabled': bool((getattr(settings, 'GROQ_API_KEY', None) or '').strip()),
    }
