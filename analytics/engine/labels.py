"""
Etiquetas legibles para la UI: convierte nombres internos de columnas/tablas
(line_total, estado_orden, sum_line_total…) en español natural (Ventas, Estado
de la orden, Total de ventas…).

Se usa SOLO en los bordes de presentación (títulos de gráficas, ejes, texto del
chat, encabezados de tablas). Nunca renombra el DataFrame de trabajo — la lógica
sigue usando los nombres reales.
"""
from __future__ import annotations
import re

# Nombres compuestos conocidos (esquema Tradeflow y afines)
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

# Tokens sueltos (se traducen palabra por palabra en nombres no conocidos)
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

# Funciones de agregación → palabra de negocio
_AGG = {"sum": "Total", "suma": "Total", "mean": "Promedio", "avg": "Promedio",
        "promedio": "Promedio", "max": "Máximo", "maximo": "Máximo",
        "min": "Mínimo", "minimo": "Mínimo", "count": "Conteo", "conteo": "Conteo"}


def agg_label(agg: str) -> str:
    return _AGG.get(str(agg).strip().lower(), str(agg).capitalize())


def pretty(name) -> str:
    """Nombre de columna/medida → etiqueta legible en español."""
    if name is None:
        return ""
    s = str(name).strip()
    if not s:
        return ""
    low = s.lower()
    if low in _ALIASES:
        return _ALIASES[low]
    # Prefijo/sufijo de agregación: "sum_line_total" / "line_total_sum" → "Total de Ventas"
    for agg, lab in _AGG.items():
        if low.startswith(agg + "_") and len(low) > len(agg) + 1:
            return f"{lab} de {pretty(s[len(agg) + 1:])}"
        if low.endswith("_" + agg) and len(low) > len(agg) + 1:
            return f"{lab} de {pretty(s[:-(len(agg) + 1)])}"
    # Sufijo _id → nombre de la entidad ("product_id" → "Producto")
    if low.endswith("_id") and len(low) > 3:
        return pretty(s[:-3])
    if low in _WORDS:
        return _WORDS[low].capitalize()
    # Nombre compuesto: traduce token por token y capitaliza la frase
    parts = [p for p in re.split(r"[_\s]+", low) if p]
    if not parts:
        return s
    words = [_WORDS.get(p, p) for p in parts]
    label = " ".join(words)
    return label[:1].upper() + label[1:]


def pretty_columns(df):
    """Devuelve una COPIA del DataFrame con columnas renombradas para mostrar.
    Evita chocar nombres: si dos columnas mapean al mismo texto, desambigua."""
    seen: set[str] = set()
    rename = {}
    for c in df.columns:
        label = pretty(c)
        if label in seen:            # colisión → conserva el nombre real para distinguir
            label = f"{label} ({c})"
        seen.add(label)
        rename[c] = label
    return df.rename(columns=rename)
