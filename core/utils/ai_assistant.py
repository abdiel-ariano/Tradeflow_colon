"""
AI Assistant para TradeFlow Colón.

Responde con datos públicos del catálogo (productos, empresas, ofertas).
Si existe GROQ_API_KEY, enriquece respuestas vía Groq; si no, usa motor local.
"""
from __future__ import annotations

import re
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from core.utils.contact import tradeflow_contact_email

SYSTEM_PROMPT = """
You are TF Assistant, assistant for TradeFlow Colón (B2B/B2C marketplace in the Colón Free Zone, Panama).
Always respond in the same language the user uses (Spanish or English).
Be clear, friendly, and concise (max. 3 short paragraphs).
Use ONLY the catalog data and SaaS plan data provided; do not invent products, stock, prices, or plan fees.
For product prices use the format indicated in the catalog (USD with two decimals).
If they ask how to buy: registration, email verification, store, and cart.
If they ask about seller plans, subscriptions, commissions, billing caps, or becoming a vendor:
use ONLY the seller SaaS plan section in context (Digitalízate, Expansión, Corporativo Pro, Ecosistema Enterprise).
If they ask about shipping or customs: indicate it depends on the seller and carrier; do not invent timelines.
If information is missing, suggest /tienda/, filters by company or category, or the public contact email provided in context.
Do not reveal user data, private orders, passwords, or API keys.
"""

_STOPWORDS = frozenset({
    'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'y', 'o', 'a',
    'que', 'qué', 'como', 'cómo', 'por', 'para', 'con', 'sin', 'es', 'son',
    'the', 'and', 'or', 'to', 'in', 'on', 'me', 'my', 'i', 'you', 'what',
    'hay', 'tiene', 'tienen', 'busco', 'buscar', 'quiero', 'necesito', 'algún',
    'algun', 'alguna', 'este', 'esta', 'estos', 'estas', 'the', 'please',
})


def _fmt_money(currency: str, amount) -> str:
    """Formatea precio para texto del asistente (USD unificado)."""
    from .money_format import format_money_usd

    cur = (currency or 'USD').strip().upper()
    if cur == 'USD':
        return format_money_usd(amount)
    try:
        val = Decimal(str(amount)).quantize(Decimal('0.01'))
    except Exception:
        val = amount
    return f'{cur} {val}'


def _product_line(product, include_link_hint: bool = False) -> str:
    """
    Una línea de texto por producto (sin datos sensibles).

    Args:
        product: instancia Product.
        include_link_hint: si True, añade pista de búsqueda en tienda.

    Returns:
        str: línea formateada.
    """
    parts = [f'• {product.name}']
    parts.append(f'({_fmt_money(product.currency, product.display_price)})')
    parts.append(f'— {product.company.name}')
    if product.category:
        parts.append(f'| {product.category.name}')
    if product.is_on_promo_now:
        parts.append(
            f'| Offer -{product.discount_pct}% '
            f'(was {_fmt_money(product.currency, product.unit_price)})'
        )
    elif product.is_bestseller:
        parts.append('| Bestseller')
    elif product.is_featured:
        parts.append('| Featured')
    line = ' '.join(parts)
    if include_link_hint:
        line += f'\n  View in store: /tienda/?buscar={product.name[:40]}'
    return line


def build_catalog_snapshot(limit_products: int = 80) -> dict:
    """
    Arma contexto del catálogo activo desde el ORM.

    Args:
        limit_products: máximo de productos en el resumen.

    Returns:
        dict: conteos, listas y texto para Groq.
    """
    from .. import merchandising as merch

    productos_qs = merch.active_products_base()
    total_productos = productos_qs.count()
    empresas_qs = (
        productos_qs.values_list('company_id', flat=True).distinct()
    )
    empresas_count = len(set(empresas_qs))
    categorias = list(
        merch.active_products_base()
        .exclude(category__isnull=True)
        .values_list('category__name', flat=True)
        .distinct()[:20]
    )

    ofertas = merch.daily_deals(8)
    bestsellers = merch.bestsellers(6)
    destacados = merch.featured_products(6)

    empresas = list(
        productos_qs.values('company__id', 'company__name')
        .distinct()
        .order_by('company__name')[:15]
    )
    empresas_nombres = [e['company__name'] for e in empresas if e.get('company__name')]

    productos_muestra = list(
        productos_qs.order_by('-merchandising_priority', 'name')[:limit_products]
    )

    lines = [
        f'Active products: {total_productos}',
        f'Companies with catalog: {empresas_count}',
        f'Categories: {", ".join(categorias[:12]) or "—"}',
    ]
    if ofertas:
        lines.append("Today's deals:")
        lines.extend(_product_line(p) for p in ofertas[:6])
    if bestsellers:
        lines.append('Bestsellers:')
        lines.extend(_product_line(p) for p in bestsellers[:5])
    if destacados:
        lines.append('Featured:')
        lines.extend(_product_line(p) for p in destacados[:5])

    return {
        'total_productos': total_productos,
        'empresas_count': empresas_count,
        'categorias': categorias,
        'empresas_nombres': empresas_nombres,
        'ofertas': ofertas,
        'bestsellers': bestsellers,
        'destacados': destacados,
        'productos_muestra': productos_muestra,
        'texto': '\n'.join(lines),
    }


def _buscar_productos(terminos: list[str], limit: int = 8):
    """Busca productos activos por palabras clave."""
    from .. import merchandising as merch

    qs = merch.active_products_base()
    if not terminos:
        return list(qs.order_by('-merchandising_priority')[:limit])

    q_obj = Q()
    for term in terminos:
        if len(term) < 2:
            continue
        q_obj |= (
            Q(name__icontains=term)
            | Q(description__icontains=term)
            | Q(sku__icontains=term)
            | Q(company__name__icontains=term)
            | Q(category__name__icontains=term)
        )
    if not q_obj:
        return list(qs.order_by('-merchandising_priority')[:limit])
    return list(qs.filter(q_obj).distinct().order_by('-merchandising_priority')[:limit])


def _tokens(mensaje: str) -> list[str]:
    """Extrae tokens útiles del mensaje."""
    raw = re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ0-9]+', mensaje.lower())
    return [t for t in raw if t not in _STOPWORDS and len(t) >= 2]


def _match_any(msg: str, keywords: tuple[str, ...]) -> bool:
    """Coincide frases completas o palabras aisladas (evita 'top' dentro de 'laptop')."""
    words = set(re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ0-9]+', msg))
    for k in keywords:
        if ' ' in k:
            if k in msg:
                return True
        elif k in words:
            return True
    return False


def responder_con_catalogo(mensaje_usuario: str, snapshot: dict | None = None) -> str:
    """
    Responde usando solo datos del catálogo (sin API externa).

    Args:
        mensaje_usuario: pregunta del usuario.
        snapshot: contexto precalculado (opcional).

    Returns:
        str: respuesta en texto.
    """
    if snapshot is None:
        snapshot = build_catalog_snapshot()

    msg = mensaje_usuario.lower().strip()
    tokens = _tokens(mensaje_usuario)
    tienda = reverse('catalogo_publico')
    signup = reverse('signup')

    if _match_any(msg, ('hola', 'buenas', 'hello', 'hi', 'saludos', 'hey')):
        return (
            'Hello! I am TF Assistant from TradeFlow Colón. '
            f'Right now there are {snapshot["total_productos"]} active products '
            f'from {snapshot["empresas_count"]} companies in the ZLC. '
            'I can help you with deals, companies, categories, and price recommendations. '
            f'Browse the catalog at {tienda} or create an account at {signup}.'
        )

    if _match_any(msg, ('zona libre', 'zlc', 'colón', 'colon', 'panamá', 'panama')):
        return (
            'TradeFlow connects buyers with companies in the Colón Free Zone (ZLC), '
            'one of the world\'s main commercial hubs. '
            f'Today we list {snapshot["total_productos"]} products from '
            f'{snapshot["empresas_count"]} verified companies. '
            f'Visit {tienda} to see the full catalog.'
        )

    if _match_any(msg, (
        'plan', 'planes', 'saas', 'suscripción', 'suscripcion', 'comisión',
        'comision', 'vendedor', 'seller', 'vender', 'digitalízate', 'digitalizate',
        'expansión', 'expansion', 'corporativo', 'enterprise', 'ecosistema',
        'facturación', 'facturacion', 'tope', 'membresía', 'membresia',
    )):
        from .saas_plan_catalog import build_saas_plans_ai_context

        return (
            'TradeFlow seller plans (ZLC):\n\n'
            f'{build_saas_plans_ai_context()}\n\n'
            f'Compare and activate from the seller portal after business sign-up ({signup}).'
        )

    if _match_any(msg, (
        'cómo compro', 'como compro', 'comprar', 'registro', 'crear cuenta',
        'carrito', 'checkout', 'pedido', 'cuenta',
    )):
        return (
            'To buy on TradeFlow: 1) Create a buyer account. '
            f'2) Browse {tienda} and filter by category or company. '
            '3) Add products to the cart and confirm your order. '
            f'Sign up at {signup}. If you already have an account, log in and go to the store.'
        )

    if _match_any(msg, (
        'oferta', 'ofertas', 'promo', 'promoción', 'promocion',
        'descuento', 'rebaja', 'rebajas', 'barato',
    )):
        ofertas = snapshot.get('ofertas') or []
        if not ofertas:
            return (
                'There are no active promotional deals right now. '
                f'Check {tienda}?tab=ofertas later or browse the full catalog.'
            )
        lines = ['These are the active deals right now:']
        lines.extend(_product_line(p) for p in ofertas[:8])
        lines.append(f'\nView all: {tienda}?tab=ofertas')
        return '\n'.join(lines)

    if _match_any(msg, (
        'más vendido', 'mas vendido', 'bestseller', 'popular', 'top',
    )):
        best = snapshot.get('bestsellers') or []
        if not best:
            return (
                'We do not have enough data for a bestseller ranking yet. '
                f'Browse featured items at {tienda}?tab=bestsellers.'
            )
        lines = ['Top-selling products recently:']
        lines.extend(_product_line(p) for p in best[:8])
        lines.append(f'\nView more: {tienda}?tab=bestsellers')
        return '\n'.join(lines)

    if _match_any(msg, ('empresa', 'empresas', 'proveedor', 'proveedores', 'vendedor')):
        nombres = snapshot.get('empresas_nombres') or []
        if not nombres:
            return f'There are no companies with active products. Check {tienda}.'
        lista = '\n'.join(f'• {n}' for n in nombres[:12])
        return (
            f'Companies with products on TradeFlow ({len(nombres)} in sample):\n'
            f'{lista}\n\nFilter by company at {tienda} (Company selector).'
        )

    if _match_any(msg, ('categoría', 'categoria', 'categorías', 'categorias')):
        cats = snapshot.get('categorias') or []
        if not cats:
            return f'There are no categories with active products. Visit {tienda}.'
        lista = '\n'.join(f'• {c}' for c in cats[:15])
        return (
            f'Available categories:\n{lista}\n\n'
            f'Use the category filter at {tienda}.'
        )

    if _match_any(msg, (
        'más barato', 'mas barato', 'menor precio', 'económico', 'economico',
        'precio bajo',
    )):
        from .. import merchandising as merch

        prods = list(
            merch.active_products_base().order_by('unit_price')[:8]
        )
        if not prods:
            return f'There are no products listed. Visit {tienda}.'
        lines = ['Most affordable options (listed):']
        lines.extend(_product_line(p) for p in prods)
        lines.append(f'\nSort in store: {tienda}?orden=precio_asc')
        return '\n'.join(lines)

    if _match_any(msg, ('destacado', 'destacados', 'recomend', 'suger')):
        dest = snapshot.get('destacados') or []
        if not dest:
            from .. import merchandising as merch
            dest = list(merch.featured_products(6))
        if dest:
            lines = ['I recommend these featured products:']
            lines.extend(_product_line(p, include_link_hint=True) for p in dest[:6])
            lines.append(f'\n{tienda}?tab=destacados')
            return '\n'.join(lines)

    # Búsqueda por palabras del mensaje
    if tokens:
        encontrados = _buscar_productos(tokens, limit=8)
        if encontrados:
            lines = [f'I found {len(encontrados)} related product(s):']
            lines.extend(_product_line(p, include_link_hint=True) for p in encontrados)
            q = '+'.join(tokens[:3])
            lines.append(f'\nSee more at {tienda}?buscar={q}')
            return '\n'.join(lines)

    # Resumen general
    if snapshot['total_productos'] == 0:
        return (
            'The catalog does not have active products yet. '
            'When inventory is published, I can recommend deals and prices. '
            f'In the meantime, email us at {tradeflow_contact_email()}.'
        )

    muestra = snapshot.get('productos_muestra') or []
    lines = [
        'I can help you with products, companies, deals, and prices in the ZLC. '
        f'Current catalog: {snapshot["total_productos"]} products, '
        f'{snapshot["empresas_count"]} companies.',
        '',
        'Some available products:',
    ]
    lines.extend(_product_line(p) for p in muestra[:6])
    lines.append(
        f'\nBrowse everything at {tienda}. Try: "deals", "companies", '
        f'"categories", or a product name.'
    )
    return '\n'.join(lines)


def _consultar_groq(mensaje_usuario: str, historial, snapshot: dict) -> str | None:
    """
    Llama a Groq con contexto del catálogo.

    Returns:
        str | None: respuesta o None si falla.
    """
    from groq import Groq

    from core.utils.saas_plan_catalog import build_saas_plans_ai_context

    client = Groq(api_key=settings.GROQ_API_KEY)
    from core.utils.contact import tradeflow_contact_email

    catalogo = snapshot.get('texto', '')[:6000]
    contact = tradeflow_contact_email()
    planes = build_saas_plans_ai_context()
    system = (
        f'{SYSTEM_PROMPT}\n\n'
        f'Public contact email: {contact}\n\n'
        f'--- Seller SaaS plans (authoritative) ---\n{planes}\n---\n\n'
        f'--- Current catalog (use only this) ---\n{catalogo}\n---'
    )
    messages = [{'role': 'system', 'content': system}]
    if historial:
        messages.extend(historial[-6:])
    messages.append({
        'role': 'user',
        'content': mensaje_usuario[:500],
    })
    model = getattr(settings, 'GROQ_MODEL', None) or 'llama-3.1-8b-instant'
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=512,
        temperature=0.45,
    )
    content = response.choices[0].message.content
    return content.strip() if content else None


# ── RAG vendedor, confianza y formato estructurado ───────────────────────────

_CATEGORY_META = {
    'productos': ('inventory_2', 'Products'),
    'ventas': ('payments', 'Sales'),
    'cotizaciones': ('request_quote', 'Quotes'),
    'catalogo': ('storefront', 'Catalog'),
    'general': ('help', 'Information'),
    'soporte': ('support_agent', 'Support'),
}

_TOPIC_KEYWORDS = {
    'productos': (
        'producto', 'productos', 'stock', 'inventario', 'sku', 'catálogo',
        'catalogo', 'artículo', 'articulo', 'publicar', 'bajo stock',
        'catalog', 'products', 'inventory', 'item', 'items',
    ),
    'ventas': (
        'venta', 'ventas', 'orden', 'órdenes', 'ordenes', 'pedido', 'pedidos',
        'ingreso', 'ingresos', 'facturación', 'facturacion', 'ticket', 'mes',
        'order', 'orders', 'sales', 'revenue',
    ),
    'cotizaciones': (
        'cotización', 'cotizacion', 'cotizaciones', 'rfq', 'propuesta',
        'responder cotización', 'aceptada', 'rechazada',
        'quote', 'quotation', 'rfq',
    ),
}


def _detect_topic(mensaje: str) -> str:
    msg = mensaje.lower()
    scores = {k: 0 for k in _TOPIC_KEYWORDS}
    words = set(_tokens(mensaje))
    for topic, kws in _TOPIC_KEYWORDS.items():
        for k in kws:
            if ' ' in k and k in msg:
                scores[topic] += 2
            elif k in words:
                scores[topic] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'catalogo'


def _html_escape(text: str) -> str:
    return (
        str(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def format_structured_response(
    categoria: str,
    bullets: list[str],
    resumen: str,
    cta: str | None = None,
    cta_url: str | None = None,
) -> str:
    """HTML seguro con encabezado, bullets, resumen y CTA opcional."""
    icon, title = _CATEGORY_META.get(categoria, _CATEGORY_META['general'])
    lines = [
        '<div class="tf-bot-card">',
        f'<div class="tf-bot-head"><span class="material-symbols-rounded">{icon}</span>'
        f'<strong>{_html_escape(title)}</strong></div>',
        '<ul class="tf-bot-list">',
    ]
    for b in bullets[:12]:
        lines.append(f'<li>{_html_escape(b)}</li>')
    lines.append('</ul>')
    if resumen:
        lines.append(f'<p class="tf-bot-summary">{_html_escape(resumen)}</p>')
    if cta:
        if cta_url:
            lines.append(
                f'<a class="tf-bot-cta" href="{_html_escape(cta_url)}">{_html_escape(cta)}</a>'
            )
        else:
            lines.append(f'<p class="tf-bot-cta-text">{_html_escape(cta)}</p>')
    lines.append('</div>')
    return ''.join(lines)


def build_seller_rag_context(company) -> dict:
    """Contexto RAG desde ORM: productos, ventas y cotizaciones del seller."""
    from datetime import timedelta

    from django.db.models import Count, Sum
    from django.utils import timezone

    from ..models import Cotizacion, Inventory, Order, OrderItem, Product

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    productos = list(
        Product.objects.filter(company=company, is_active=True)
        .select_related('category')[:40]
    )
    bajo = []
    for inv in Inventory.objects.filter(product__company=company).select_related('product')[:50]:
        if inv.is_low_stock:
            bajo.append(inv.product.name)

    vendidos = set(
        OrderItem.objects.filter(product__company=company)
        .values_list('product_id', flat=True)
    )
    sin_ventas = [p.name for p in productos if p.pk not in vendidos][:8]

    items_mes = OrderItem.objects.filter(
        product__company=company,
        order__created_at__gte=month_start,
        order__status__in=('paid', 'packed', 'shipped', 'delivered'),
    )
    ingresos = items_mes.aggregate(t=Sum('line_total'))['t'] or Decimal('0')
    ordenes_mes = (
        Order.objects.filter(items__product__company=company, created_at__gte=month_start)
        .distinct()
        .count()
    )

    cot_qs = Cotizacion.objects.filter(empresa=company)
    cot_mes = cot_qs.filter(created_at__gte=month_start).count()
    cot_pend = cot_qs.filter(estado='pendiente').count()
    cot_recientes = list(
        cot_qs.select_related('buyer').order_by('-created_at')[:8]
    )

    return {
        'company': company,
        'company_name': company.name,
        'productos': productos,
        'bajo_stock': bajo,
        'sin_ventas': sin_ventas,
        'ingresos_mes': ingresos,
        'ordenes_mes': ordenes_mes,
        'cot_mes': cot_mes,
        'cot_pend': cot_pend,
        'cot_recientes': cot_recientes,
    }


def _seller_rag_answer(mensaje: str, ctx: dict, topic: str) -> tuple[list[str], str, float, str | None]:
    """
    Genera bullets, resumen, confianza (0-1) y tema para fallback.

    Returns:
        bullets, resumen, confianza, tema_label
    """
    tokens = _tokens(mensaje)
    bullets: list[str] = []
    conf = 0.45
    tema = _CATEGORY_META.get(topic, _CATEGORY_META['general'])[1]

    if topic == 'productos':
        conf += 0.25
        bullets.append(f'Total active in your company: {len(ctx["productos"])}')
        if ctx['bajo_stock']:
            conf += 0.2
            bullets.extend(f'Low stock: {n}' for n in ctx['bajo_stock'][:6])
        if ctx['sin_ventas']:
            conf += 0.15
            bullets.append(f'No sales yet: {", ".join(ctx["sin_ventas"][:5])}')
        encontrados = [
            p for p in ctx['productos']
            if any(t in p.name.lower() for t in tokens)
        ]
        if encontrados:
            conf += 0.25
            for p in encontrados[:6]:
                bullets.append(f'{p.name} — {_fmt_money(p.currency, p.display_price)} (code {p.sku or "—"})')
        elif tokens and not encontrados:
            conf -= 0.2

    elif topic == 'ventas':
        from ..models import Order as OrderModel

        conf += 0.35
        bullets.append(f'Orders this month: {ctx["ordenes_mes"]}')
        bullets.append(f'Delivered/paid revenue this month: USD {ctx["ingresos_mes"]}')
        company = ctx['company']
        recientes = (
            OrderModel.objects.filter(items__product__company=company)
            .distinct()
            .select_related('buyer')
            .order_by('-created_at')[:5]
        )
        for o in recientes:
            buyer = o.buyer.get_full_name() or o.buyer.username
            bullets.append(f'{o.order_number} — {buyer} — {o.get_status_display()} — {o.created_at:%d/%m/%Y}')
        if any(t in ('orden', 'ordenes', 'órdenes', 'tf-') for t in tokens):
            conf += 0.15

    elif topic == 'cotizaciones':
        conf += 0.35
        bullets.append(f'Quotes this month: {ctx["cot_mes"]}')
        bullets.append(f'Awaiting response: {ctx["cot_pend"]}')
        for cot in ctx['cot_recientes'][:6]:
            buyer = cot.buyer.get_full_name() or cot.buyer.username
            bullets.append(f'{cot.numero} — {buyer} — {cot.get_estado_display()}')
        if tokens:
            match = [
                c for c in ctx['cot_recientes']
                if any(t in c.numero.lower() for t in tokens)
            ]
            if match:
                conf += 0.2

    resumen = (
        f'Summary: data for {ctx["company_name"]} from your seller dashboard. '
        'See My Dashboard for full details.'
    )
    return bullets, resumen, min(conf, 1.0), tema


def responder_seller_rag(mensaje: str, company) -> dict:
    """Respuesta estructurada para vendedor con umbral de confianza 85%."""
    ctx = build_seller_rag_context(company)
    topic = _detect_topic(mensaje)
    bullets, resumen, conf, tema_label = _seller_rag_answer(mensaje, ctx, topic)

    if not bullets:
        bullets.append(f'Company: {ctx["company_name"]}')
    if len(bullets) < 2:
        bullets.append('Review the Products, Sales, and Quotes sections in your dashboard.')
    if topic in ('productos', 'ventas', 'cotizaciones') and len(bullets) >= 2:
        conf = max(conf, 0.87)

    if conf < 0.85:
        fallback = (
            f'I do not have enough information about {tema_label}. '
            'Would you like me to connect you with support?'
        )
        html = format_structured_response(
            'soporte',
            [fallback],
            f'Email {tradeflow_contact_email()} or use the contact form.',
            'Contact support',
            f'mailto:{tradeflow_contact_email()}',
        )
        return {
            'respuesta': fallback,
            'respuesta_html': html,
            'confianza': conf,
            'categoria': 'soporte',
            'baja_confianza': True,
        }

    cta_map = {
        'productos': ('View my products', reverse('seller_mis_productos')),
        'ventas': ('View my sales', reverse('seller_mis_ventas')),
        'cotizaciones': ('View quotes', reverse('seller_cotizaciones')),
    }
    cta_label, cta_url = cta_map.get(topic, ('Go to My Dashboard', reverse('portal_seller')))

    html = format_structured_response(topic, bullets, resumen[:200], cta_label, cta_url)
    plain = '\n'.join(['• ' + b for b in bullets] + ['', resumen[:200], '', cta_label])
    return {
        'respuesta': plain,
        'respuesta_html': html,
        'confianza': conf,
        'categoria': topic,
        'baja_confianza': False,
    }


def _catalog_to_structured(mensaje: str, snapshot: dict) -> dict:
    """Convierte respuesta de catálogo a formato estructurado con confianza."""
    raw = responder_con_catalogo(mensaje, snapshot)
    topic = _detect_topic(mensaje)
    if topic in ('productos', 'ventas', 'cotizaciones'):
        topic = 'catalogo'

    lines = [ln.strip() for ln in raw.split('\n') if ln.strip()]
    bullets = [ln.lstrip('•').strip() for ln in lines if ln.startswith('•')][:10]
    if not bullets:
        bullets = lines[1:7] if len(lines) > 1 else lines[:4]

    conf = 0.72
    tokens = _tokens(mensaje)
    if tokens and any(t in raw.lower() for t in tokens):
        conf = 0.88
    if (
        'There are no' in raw or 'there are no' in raw
        or 'We do not have' in raw or 'The catalog does not have' in raw
        or 'not found' in raw.lower()
    ):
        conf = 0.55

    resumen = lines[0][:180] if lines else 'TradeFlow Colón catalog information.'
    tienda = reverse('catalogo_publico')

    if conf < 0.85:
        tema = _CATEGORY_META.get(topic, _CATEGORY_META['catalogo'])[1]
        fb = f'I do not have enough information about {tema}. Would you like me to connect you with support?'
        return {
            'respuesta': fb,
            'respuesta_html': format_structured_response(
                'soporte',
                [fb],
                'Browse the store or contact support.',
                'Contact support',
                f'mailto:{tradeflow_contact_email()}',
            ),
            'confianza': conf,
            'categoria': 'soporte',
            'baja_confianza': True,
        }

    html = format_structured_response(
        topic,
        bullets,
        resumen[:200],
        'Browse store',
        tienda,
    )
    return {
        'respuesta': raw,
        'respuesta_html': html,
        'confianza': conf,
        'categoria': topic,
        'baja_confianza': False,
    }


def consultar_asistente(mensaje_usuario, historial=None, user=None, company=None):
    """
    Motor RAG + formato estructurado. Devuelve dict con texto, HTML y confianza.

    historial: últimos mensajes (máx. 5 en API).
    user/company: activan RAG de vendedor si hay empresa vinculada.
    """
    mensaje = (mensaje_usuario or '').strip()
    if not mensaje:
        empty = 'Type your question and I will help you with the ZLC catalog.'
        return {
            'respuesta': empty,
            'respuesta_html': format_structured_response('general', [empty], '', None),
            'confianza': 1.0,
            'categoria': 'general',
            'baja_confianza': False,
        }

    historial = (historial or [])[-5:]

    if company is not None:
        topic = _detect_topic(mensaje)
        if topic in ('productos', 'ventas', 'cotizaciones') or _match_any(
            mensaje.lower(),
            _TOPIC_KEYWORDS['productos'] + _TOPIC_KEYWORDS['ventas'] + _TOPIC_KEYWORDS['cotizaciones'],
        ):
            return responder_seller_rag(mensaje, company)

    snapshot = build_catalog_snapshot()
    result = _catalog_to_structured(mensaje, snapshot)

    api_key = (getattr(settings, 'GROQ_API_KEY', None) or '').strip()
    if api_key and not result.get('baja_confianza'):
        try:
            groq_resp = _consultar_groq(mensaje, historial, snapshot)
            if groq_resp:
                bullets = [groq_resp[:400]]
                result['respuesta'] = groq_resp
                result['respuesta_html'] = format_structured_response(
                    result['categoria'],
                    bullets,
                    groq_resp[:200] if len(groq_resp) > 200 else '',
                    'View store',
                    reverse('catalogo_publico'),
                )
                result['confianza'] = 0.9
        except Exception as exc:
            import logging
            logging.getLogger('tradeflow.ai').warning('Groq no disponible: %s', exc)

    return result
