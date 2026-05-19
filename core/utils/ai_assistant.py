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

SYSTEM_PROMPT = """
Eres TF Assistant, asistente de TradeFlow Colón (marketplace Zona Libre de Colón, Panamá).
Responde SIEMPRE en el mismo idioma que usa el usuario. Si escribe en inglés, responde en inglés.
Si escribe en español, responde en español. Detecta el idioma automáticamente.
Sé conciso (máx. 3 párrafos).
Usa SOLO los datos del catálogo proporcionados; no inventes productos ni precios.
Si falta información, sugiere explorar la tienda o info@tradeflow.pa.
No reveles datos de usuarios, órdenes privadas ni credenciales.
"""

_STOPWORDS = frozenset({
    'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'y', 'o', 'a',
    'que', 'qué', 'como', 'cómo', 'por', 'para', 'con', 'sin', 'es', 'son',
    'the', 'and', 'or', 'to', 'in', 'on', 'me', 'my', 'i', 'you', 'what',
    'hay', 'tiene', 'tienen', 'busco', 'buscar', 'quiero', 'necesito', 'algún',
    'algun', 'alguna', 'este', 'esta', 'estos', 'estas', 'the', 'please',
})


def _fmt_money(currency: str, amount) -> str:
    """Formatea precio para texto del asistente."""
    try:
        val = Decimal(str(amount)).quantize(Decimal('0.01'))
    except Exception:
        val = amount
    return f'{currency} {val}'


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
            f'| Oferta -{product.discount_pct}% '
            f'(antes {_fmt_money(product.currency, product.unit_price)})'
        )
    elif product.is_bestseller:
        parts.append('| Más vendido')
    elif product.is_featured:
        parts.append('| Destacado')
    line = ' '.join(parts)
    if include_link_hint:
        line += f'\n  Ver en tienda: /tienda/?buscar={product.name[:40]}'
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
        f'Productos activos: {total_productos}',
        f'Empresas con catálogo: {empresas_count}',
        f'Categorías: {", ".join(categorias[:12]) or "—"}',
    ]
    if ofertas:
        lines.append('Ofertas del día:')
        lines.extend(_product_line(p) for p in ofertas[:6])
    if bestsellers:
        lines.append('Más vendidos:')
        lines.extend(_product_line(p) for p in bestsellers[:5])
    if destacados:
        lines.append('Destacados:')
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
    tienda = reverse('tienda')
    signup = reverse('signup')

    if _match_any(msg, ('hola', 'buenas', 'hello', 'hi', 'saludos', 'hey')):
        return (
            '¡Hola! Soy TF Assistant de TradeFlow Colón. '
            f'En este momento hay {snapshot["total_productos"]} productos activos '
            f'de {snapshot["empresas_count"]} empresas en la ZLC. '
            'Puedo ayudarte con ofertas, empresas, categorías y recomendaciones de precio. '
            f'Explora el catálogo en {tienda} o crea cuenta en {signup}.'
        )

    if _match_any(msg, ('zona libre', 'zlc', 'colón', 'colon', 'panamá', 'panama')):
        return (
            'TradeFlow conecta compradores con empresas de la Zona Libre de Colón (ZLC), '
            'uno de los principales hubs comerciales del mundo. '
            f'Hoy listamos {snapshot["total_productos"]} productos de '
            f'{snapshot["empresas_count"]} empresas verificadas. '
            f'Visita {tienda} para ver el catálogo completo.'
        )

    if _match_any(msg, (
        'cómo compro', 'como compro', 'comprar', 'registro', 'crear cuenta',
        'carrito', 'checkout', 'pedido', 'cuenta',
    )):
        return (
            'Para comprar en TradeFlow: 1) Crea una cuenta comprador. '
            f'2) Explora {tienda} y filtra por categoría o empresa. '
            '3) Agrega productos al carrito y confirma el pedido. '
            f'Regístrate en {signup}. Si ya tienes cuenta, inicia sesión y entra a la tienda.'
        )

    if _match_any(msg, (
        'oferta', 'ofertas', 'promo', 'promoción', 'promocion',
        'descuento', 'rebaja', 'rebajas', 'barato',
    )):
        ofertas = snapshot.get('ofertas') or []
        if not ofertas:
            return (
                'No hay ofertas con promoción vigente en este momento. '
                f'Revisa {tienda}?tab=ofertas más tarde o explora el catálogo completo.'
            )
        lines = ['Estas son las ofertas activas ahora:']
        lines.extend(_product_line(p) for p in ofertas[:8])
        lines.append(f'\nVer todas: {tienda}?tab=ofertas')
        return '\n'.join(lines)

    if _match_any(msg, (
        'más vendido', 'mas vendido', 'bestseller', 'popular', 'top',
    )):
        best = snapshot.get('bestsellers') or []
        if not best:
            return (
                'Aún no hay ranking de más vendidos con datos suficientes. '
                f'Explora destacados en {tienda}?tab=bestsellers.'
            )
        lines = ['Productos más vendidos recientemente:']
        lines.extend(_product_line(p) for p in best[:8])
        lines.append(f'\nVer más: {tienda}?tab=bestsellers')
        return '\n'.join(lines)

    if _match_any(msg, ('empresa', 'empresas', 'proveedor', 'proveedores', 'vendedor')):
        nombres = snapshot.get('empresas_nombres') or []
        if not nombres:
            return f'No hay empresas con productos activos. Consulta {tienda}.'
        lista = '\n'.join(f'• {n}' for n in nombres[:12])
        return (
            f'Empresas con productos en TradeFlow ({len(nombres)} en muestra):\n'
            f'{lista}\n\nFiltra por empresa en {tienda} (selector Empresa).'
        )

    if _match_any(msg, ('categoría', 'categoria', 'categorías', 'categorias')):
        cats = snapshot.get('categorias') or []
        if not cats:
            return f'No hay categorías con productos activos. Visita {tienda}.'
        lista = '\n'.join(f'• {c}' for c in cats[:15])
        return (
            f'Categorías disponibles:\n{lista}\n\n'
            f'Usa el filtro de categoría en {tienda}.'
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
            return f'No hay productos listados. Visita {tienda}.'
        lines = ['Opciones con precio más accesible (lista):']
        lines.extend(_product_line(p) for p in prods)
        lines.append(f'\nOrdenar en tienda: {tienda}?orden=precio_asc')
        return '\n'.join(lines)

    if _match_any(msg, ('destacado', 'destacados', 'recomend', 'suger')):
        dest = snapshot.get('destacados') or []
        if not dest:
            from .. import merchandising as merch
            dest = list(merch.featured_products(6))
        if dest:
            lines = ['Te recomiendo estos productos destacados:']
            lines.extend(_product_line(p, include_link_hint=True) for p in dest[:6])
            lines.append(f'\n{tienda}?tab=destacados')
            return '\n'.join(lines)

    # Búsqueda por palabras del mensaje
    if tokens:
        encontrados = _buscar_productos(tokens, limit=8)
        if encontrados:
            lines = [f'Encontré {len(encontrados)} producto(s) relacionado(s):']
            lines.extend(_product_line(p, include_link_hint=True) for p in encontrados)
            q = '+'.join(tokens[:3])
            lines.append(f'\nVer más en {tienda}?buscar={q}')
            return '\n'.join(lines)

    # Resumen general
    if snapshot['total_productos'] == 0:
        return (
            'El catálogo aún no tiene productos activos. '
            'Cuando haya inventario publicado, podré recomendarte ofertas y precios. '
            f'Mientras tanto escríbenos a info@tradeflow.pa.'
        )

    muestra = snapshot.get('productos_muestra') or []
    lines = [
        'Puedo ayudarte con productos, empresas, ofertas y precios de la ZLC. '
        f'Catálogo actual: {snapshot["total_productos"]} productos, '
        f'{snapshot["empresas_count"]} empresas.',
        '',
        'Algunos productos disponibles:',
    ]
    lines.extend(_product_line(p) for p in muestra[:6])
    lines.append(
        f'\nExplora todo en {tienda}. Prueba: "ofertas", "empresas", '
        f'"categorías" o el nombre de un producto.'
    )
    return '\n'.join(lines)


def _consultar_groq(mensaje_usuario: str, historial, snapshot: dict) -> str | None:
    """
    Llama a Groq con contexto del catálogo.

    Returns:
        str | None: respuesta o None si falla.
    """
    from groq import Groq

    client = Groq(api_key=settings.GROQ_API_KEY)
    catalogo = snapshot.get('texto', '')[:6000]
    system = (
        f'{SYSTEM_PROMPT}\n\n'
        f'--- Catálogo actual (usa solo esto) ---\n{catalogo}\n---'
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


def consultar_asistente(mensaje_usuario, historial=None):
    """
    Responde al usuario: motor local con catálogo ORM; Groq opcional si hay API key.

    Args:
        mensaje_usuario: pregunta del usuario.
        historial: mensajes previos para Groq (opcional).

    Returns:
        str: respuesta del asistente.
    """
    mensaje = (mensaje_usuario or '').strip()
    if not mensaje:
        return 'Escribe tu pregunta y te ayudo con el catálogo ZLC.'

    snapshot = build_catalog_snapshot()
    respuesta_local = responder_con_catalogo(mensaje, snapshot)

    api_key = (getattr(settings, 'GROQ_API_KEY', None) or '').strip()
    if not api_key:
        return respuesta_local

    try:
        groq_resp = _consultar_groq(mensaje, historial, snapshot)
        if groq_resp:
            return groq_resp
    except Exception:
        pass

    return respuesta_local
