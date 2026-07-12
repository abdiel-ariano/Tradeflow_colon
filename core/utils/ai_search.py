"""
Búsqueda inteligente estilo Google para TradeFlow.

Combina coincidencia local (ORM) con enriquecimiento opcional vía Groq:
sugerencias, consultas relacionadas y tips contextuales.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse

log = logging.getLogger('tradeflow.ai_search')

_STOPWORDS = frozenset({
    'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'y', 'o', 'a',
    'the', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'buscar', 'search',
    'quiero', 'need', 'find', 'show', 'me', 'my', 'product', 'producto',
})


def _tokens(q: str) -> list[str]:
    raw = re.findall(r'[\wáéíóúüñ]+', (q or '').lower(), flags=re.UNICODE)
    return [t for t in raw if len(t) >= 2 and t not in _STOPWORDS]


def _item(kind: str, label: str, url: str, *, subtitle: str = '', icon: str = 'search', score: int = 0):
    return {
        'type': kind,
        'label': label,
        'subtitle': subtitle,
        'url': url,
        'icon': icon,
        'score': score,
    }


def _product_subtitle(product) -> str:
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
    from .. import merchandising as merch
    from ..models import Category, Company, Product

    q = (query or '').strip()
    if not q:
        trending = []
        for p in merch.featured_products(4):
            trending.append(_item(
                'product',
                p.name,
                f"{reverse('catalogo_publico')}?buscar={p.name[:50]}",
                subtitle=_product_subtitle(p),
                icon='inventory_2',
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
        _item(
            'product',
            p.name,
            f"{reverse('catalogo_publico')}?buscar={p.name[:50]}",
            subtitle=_product_subtitle(p),
            icon='inventory_2',
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
        results.append(_item(
            'product',
            p.name,
            reverse('seller_editar_producto', args=[p.pk]),
            subtitle=_product_subtitle(p),
            icon='inventory_2',
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
    from .. import merchandising as merch

    q = (query or '').strip()
    profile = getattr(user, 'profile', None) if user and user.is_authenticated else None

    if not q and profile:
        for row in merch.buyer_deep_search_suggestions(profile, limit=limit):
            p = row['product']
            results = [
                _item(
                    'product',
                    p.name,
                    row['url'],
                    subtitle=row.get('label', ''),
                    icon='auto_awesome',
                    score=50,
                )
            ]
            return results

    return search_public(q, limit=limit)


def search_admin(query: str, limit: int = 8) -> list[dict]:
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
        results.append(_item(
            'product',
            p.name,
            f"{reverse('productos')}?buscar={q}",
            subtitle=f'{p.company.name} · {p.sku or "—"}',
            icon='inventory_2',
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
