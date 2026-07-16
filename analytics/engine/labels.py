"""Human-readable labels for analytics UI edges (charts, chat, tables).

Maps internal column/metric names (line_total, estado_orden, sum_*) to
natural Spanish or English without renaming the working DataFrame.
"""
from __future__ import annotations
import re

# Known compound names (TradeFlow schema and aliases)
_ALIASES_EN = {
    "line_total": "Sales",
    "total_orden": "Order total",
    "order_total": "Order total",
    "unit_price_snapshot": "Unit price",
    "unit_price": "Unit price",
    "estado_orden": "Order status",
    "tipo_orden": "Order type",
    "order_number": "Order #",
    "created_at": "Date",
    "producto": "Product",
    "categoria": "Category",
    "orden": "Order",
    "fecha": "Date",
    "qty": "Units",
    "dia": "Day",
}

_WORDS_EN = {
    "producto": "product", "productos": "products", "product": "product",
    "categoria": "category", "category": "category",
    "orden": "order", "order": "order", "ordenes": "orders",
    "estado": "status", "status": "status", "tipo": "type", "type": "type",
    "fecha": "date", "date": "date", "dia": "day", "mes": "month",
    "qty": "units", "cantidad": "quantity", "unidades": "units",
    "precio": "price", "price": "price", "total": "total", "subtotal": "subtotal",
    "sku": "SKU", "cliente": "customer", "customer": "customer",
    "ventas": "sales", "venta": "sale", "ingreso": "revenue", "ingresos": "revenue",
    "monto": "amount", "importe": "amount", "nombre": "name", "name": "name",
    "empresa": "company", "company": "company", "id": "ID",
}

_AGG_EN = {"sum": "Total", "suma": "Total", "mean": "Average", "avg": "Average",
          "promedio": "Average", "max": "Max", "maximo": "Max",
          "min": "Min", "minimo": "Min", "count": "Count", "conteo": "Count"}

_ALIASES = {
    "line_total": "Ventas",
    "total_orden": "Total de la orden",
    "order_total": "Total de la orden",
    "unit_price_snapshot": "Precio unitario",
    "unit_price": "Precio unitario",
    "estado_orden": "Estado de la orden",
    "tipo_orden": "Tipo de orden",
    "order_number": "N.º de orden",
    "created_at": "Fecha",
}

# Loose tokens (word-by-word for unknown names)
_WORDS = {
    "producto": "producto", "productos": "productos", "product": "producto",
    "categoria": "categoría", "category": "categoría",
    "orden": "orden", "order": "orden", "ordenes": "órdenes",
    "estado": "estado", "status": "estado", "tipo": "tipo", "type": "tipo",
    "fecha": "fecha", "date": "fecha", "dia": "día", "mes": "mes",
    "qty": "unidades", "cantidad": "cantidad", "unidades": "unidades",
    "precio": "precio", "price": "precio", "total": "total", "subtotal": "subtotal",
    "sku": "SKU", "cliente": "cliente", "customer": "cliente",
    "ventas": "ventas", "venta": "venta", "ingreso": "ingreso", "ingresos": "ingresos",
    "monto": "monto", "importe": "importe", "nombre": "nombre", "name": "nombre",
    "empresa": "empresa", "company": "empresa", "id": "ID",
}

# Aggregation verbs → business wording
_AGG = {"sum": "Total", "suma": "Total", "mean": "Promedio", "avg": "Promedio",
        "promedio": "Promedio", "max": "Máximo", "maximo": "Máximo",
        "min": "Mínimo", "minimo": "Mínimo", "count": "Conteo", "conteo": "Conteo"}


def agg_label(agg: str) -> str:
    """Map an aggregation verb to a short business label."""
    return _AGG.get(str(agg).strip().lower(), str(agg).capitalize())


def pretty(name, lang: str = "es") -> str:
    """Map a column/metric name to a human label (es|en)."""
    if name is None:
        return ""
    s = str(name).strip()
    if not s:
        return ""
    low = s.lower()
    aliases = _ALIASES_EN if lang == "en" else _ALIASES
    words = _WORDS_EN if lang == "en" else _WORDS
    aggs = _AGG_EN if lang == "en" else _AGG
    if low in aliases:
        return aliases[low]
    for agg, lab in aggs.items():
        if low.startswith(agg + "_") and len(low) > len(agg) + 1:
            join = " of " if lang == "en" else " de "
            return f"{lab}{join}{pretty(s[len(agg) + 1:], lang=lang)}"
        if low.endswith("_" + agg) and len(low) > len(agg) + 1:
            join = " of " if lang == "en" else " de "
            return f"{lab}{join}{pretty(s[:-(len(agg) + 1)], lang=lang)}"
    if low.endswith("_id") and len(low) > 3:
        return pretty(s[:-3], lang=lang)
    if low in words:
        return words[low].capitalize()
    parts = [p for p in re.split(r"[_\s]+", low) if p]
    if not parts:
        return s
    out = " ".join(words.get(p, p) for p in parts)
    return out[:1].upper() + out[1:]


def pretty_columns(df, lang: str = "es"):
    """Return a COPY of df with display column names (es|en)."""
    seen: set[str] = set()
    rename = {}
    for c in df.columns:
        label = pretty(c, lang=lang)
        if label in seen:
            label = f"{label} ({c})"
        seen.add(label)
        rename[c] = label
    return df.rename(columns=rename)
