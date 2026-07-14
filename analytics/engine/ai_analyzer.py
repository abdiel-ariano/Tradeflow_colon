from __future__ import annotations
import json
import os
import re
import difflib
from functools import lru_cache
import pandas as pd
from openai import OpenAI
from . import chart_generator as cg
from . import forecasting
from . import labels as L

# ── Proveedor LLM: NVIDIA NIM (API compatible con OpenAI) ────────────────────
# Contenedor self-hosted: nvcr.io/nim/meta/llama-3.3-70b-instruct:latest
#   al correr expone  http://localhost:8000/v1  y sirve  meta/llama-3.3-70b-instruct
# Todo es configurable por entorno para poder apuntar también a la API en la
# nube de NVIDIA (https://integrate.api.nvidia.com/v1 con NVIDIA_API_KEY) sin
# tocar código:
#   LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (o NVIDIA_API_KEY)
DEFAULT_LLM_BASE_URL = "http://localhost:8000/v1"
DEFAULT_LLM_MODEL    = "meta/llama-3.3-70b-instruct"


def _base_url() -> str:
    return os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_LLM_BASE_URL


def _llm_api_key(explicit: str = "") -> str:
    # NIM self-hosted NO exige key (servidor local); el cliente OpenAI sí requiere
    # un string no vacío, de ahí el placeholder "not-needed".
    return (explicit or os.getenv("LLM_API_KEY", "") or os.getenv("NVIDIA_API_KEY", "")
            or "not-needed")


def _models() -> list[str]:
    # El contenedor sirve UN modelo; se admite override y lista separada por comas
    # (p. ej. para una cadena de fallback contra la API en la nube).
    raw = os.getenv("LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL
    return [m.strip() for m in raw.split(",") if m.strip()]


def _llm_enabled() -> bool:
    """True si hay un endpoint LLM configurado. Con NIM self-hosted siempre lo
    hay; si el contenedor no está arriba, la llamada falla y se responde con un
    aviso amable. Poner LLM_BASE_URL=' ' (vacío tras strip no aplica) no lo apaga:
    para forzar modo offline, exportar LLM_OFFLINE=1."""
    return os.getenv("LLM_OFFLINE", "").strip() not in ("1", "true", "True")

# Frases que delatan que el modelo filtró su razonamiento interno (en inglés,
# aunque le pedimos español) en vez de dar la respuesta final.
_REASONING_MARKERS = (
    "we need to", "the user wants", "the user says", "the user is asking",
    "the user probably", "let me ", "let's ", "based only on", "max 4 sentences",
    "we can ", "we should", "i need to", "we have to", "provide a", "okay,",
)


def _looks_like_reasoning(text: str) -> bool:
    low = (text or "").lower()
    return sum(1 for m in _REASONING_MARKERS if m in low) >= 2

# ── Tool definitions — el modelo DEBE llamar una de estas ─────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_chart",
            "description": (
                "Crea una gráfica/visualización de los datos. "
                "Usar cuando el usuario pida gráfica, chart, visualización, "
                "histograma, dispersión, barras, pastel, línea, boxplot, correlación."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["barras", "histograma", "dispersion", "linea",
                                 "pastel", "boxplot", "barras_agrupadas", "correlacion",
                                 "treemap", "sunburst", "funnel", "gauge"],
                        "description": "Tipo de gráfica a generar",
                    },
                    "x": {"type": "string", "description": "Nombre exacto de la columna para eje X o columna principal"},
                    "y": {"type": "string", "description": "Nombre exacto de la columna numérica para eje Y"},
                    "color": {"type": "string", "description": "Columna categórica para diferenciar por color (opcional)"},
                    "agrupar_por": {"type": "string", "description": "Columna para agrupar (barras_agrupadas)"},
                    "agregar": {
                        "type": "string",
                        "enum": ["sum", "mean", "count", "max", "min"],
                        "description": "Función de agregación",
                    },
                    "top_n": {"type": "integer", "description": "Limitar a los N valores principales"},
                    "titulo": {"type": "string", "description": "Título descriptivo para la gráfica"},
                    "comentario": {"type": "string", "description": "Breve comentario sobre la gráfica (1 oración)"},
                },
                "required": ["tipo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_table",
            "description": (
                "Crea una tabla de datos. "
                "Usar cuando el usuario pida tabla, ranking, top N, listado, "
                "agrupar, filtrar, estadísticas, resumen, ordenar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operacion": {
                        "type": "string",
                        "enum": ["filter", "groupby", "sort", "describe",
                                 "value_counts", "crosstab", "pivot"],
                        "description": "Tipo de operación sobre los datos",
                    },
                    "columnas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columnas a incluir en el resultado",
                    },
                    "filtros": {
                        "type": "object",
                        "description": "Filtros: {columna: valor} o {columna: {op: '>', val: 100}}",
                    },
                    "agrupar_por": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columnas para agrupar (groupby)",
                    },
                    "agregar": {
                        "type": "object",
                        "description": "Agregaciones: {columna: 'sum'|'mean'|'count'|'max'|'min'}",
                    },
                    "ordenar_por": {"type": "string", "description": "Columna para ordenar el resultado"},
                    "ascendente": {"type": "boolean", "description": "True = ascendente, False = descendente"},
                    "top_n": {"type": "integer", "description": "Número máximo de filas a mostrar"},
                    "col1": {"type": "string", "description": "Primera columna para crosstab"},
                    "col2": {"type": "string", "description": "Segunda columna para crosstab o pivot"},
                    "comentario": {"type": "string", "description": "Breve comentario sobre la tabla (1 oración)"},
                },
                "required": ["operacion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": (
                "Responde una pregunta general o análisis sobre los datos. "
                "Usar SOLO cuando no se pide gráfica ni tabla."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "respuesta": {
                        "type": "string",
                        "description": "Respuesta concisa en español (máximo 3 oraciones)",
                    }
                },
                "required": ["respuesta"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Eres un analista de datos experto. Responde SIEMPRE en español, claro y "
    "conciso (máximo 4 oraciones). Básate ÚNICAMENTE en los datos del contexto "
    "(esquema, estadísticas y muestra); usa números concretos cuando ayuden. "
    "Si la pregunta no se puede responder con esos datos, dilo brevemente."
)

# ── Palabras clave para detección rápida (sin LLM) ──────────────────────────
_CHART_WORDS = {
    "gráfica", "grafica", "gráfico", "grafico", "chart", "plot",
    "visualiza", "visualización", "visualizacion", "grafícame", "graficame",
    "histograma", "barras", "dispersión", "dispersion",
    "pastel", "pie", "circular", "dona", "donut", "torta",
    "línea", "linea", "lineas", "tendencia", "evolución", "evolucion",
    "boxplot", "bigotes",
    "correlación", "correlacion", "scatter", "heatmap", "mapa de calor",
    "distribución", "distribucion", "distribuye", "distribuyen",
    "muéstrame", "muestrame", "nube de puntos", "diagrama",
    "treemap", "árbol", "arbol", "sunburst", "jerarquía", "jerarquia",
    "embudo", "funnel", "medidor", "gauge", "indicador",
    "desglosa", "desglósame", "desglosame", "desglose", "desglosar",
    "desglosado", "desglosados", "segmenta", "segmentado",
}
_TABLE_WORDS = {
    "tabla", "top", "ranking", "lista", "listado", "agrupa", "filtra",
    "ordena", "muestra", "estadísticas", "estadisticas", "resumen", "pivot",
    "cruce", "frecuencia", "conteo", "cuenta", "promedio por", "suma por",
    "máximo por", "maximo por", "mínimo por", "minimo por",
}
# Palabras de tabla que ganan siempre aunque también haya palabras de gráfica
_STRONG_TABLE_WORDS = {"ranking", "tabla", "estadísticas", "estadisticas",
                       "pivot", "cruce"}
# Palabras que dicen inequívocamente "quiero una gráfica" (ganan sobre 'top').
_STRONG_CHART_WORDS = {"gráfica", "grafica", "gráfico", "grafico", "chart", "plot",
                       "barras", "pastel", "circular", "dona", "torta", "histograma",
                       "dispersión", "dispersion", "scatter", "treemap", "sunburst",
                       "boxplot", "línea", "linea", "embudo", "medidor", "correlación",
                       "correlacion", "visualiza", "graficame", "grafícame"}
# Orden: tipos específicos primero; "barras" al final (es el default).
_CHART_TYPE_MAP = {
    "treemap": "treemap", "árbol": "treemap", "arbol": "treemap", "mapa de arbol": "treemap",
    "sunburst": "sunburst", "jerarquía": "sunburst", "jerarquia": "sunburst",
    "embudo": "funnel", "funnel": "funnel",
    "medidor": "gauge", "gauge": "gauge", "indicador": "gauge", "velocímetro": "gauge",
    "histograma": "histograma",
    "distribución": "histograma", "distribucion": "histograma",
    "distribuye": "histograma", "distribuyen": "histograma",
    "dispersión": "dispersion", "dispersion": "dispersion", "scatter": "dispersion",
    "nube de puntos": "dispersion",
    "diagrama de caja": "boxplot", "boxplot": "boxplot", "box plot": "boxplot",
    "caja y bigote": "boxplot", "bigotes": "boxplot", "caja": "boxplot", "box": "boxplot",
    "correlación": "correlacion", "correlacion": "correlacion",
    "mapa de calor": "correlacion", "heatmap": "correlacion",
    "línea": "linea", "linea": "linea", "lineas": "linea",
    "tendencia": "linea", "evolución": "linea", "evolucion": "linea",
    "serie de tiempo": "linea", "serie temporal": "linea",
    # circulares / pastel  (la causa del bug: "circular" no estaba)
    "pastel": "pastel", "pie": "pastel", "circular": "pastel",
    "círculo": "pastel", "circulo": "pastel", "dona": "pastel",
    "donut": "pastel", "torta": "pastel", "anillo": "pastel",
    # barras (default, al final)
    "barras agrupadas": "barras_agrupadas", "agrupadas": "barras_agrupadas",
    "barras": "barras", "barra": "barras", "columnas": "barras",
}


_QUESTION_OVERRIDE_WORDS = (
    "que opinas", "qué opinas", "que piensas", "qué piensas", "que crees",
    "qué crees", "como ves", "cómo ves", "tu opinion", "tu opinión",
    "me recomiendas", "recomendacion", "recomendación", "sugerencia",
    "sugerencias", "consejo", "consejos", "analisis general", "análisis general",
    "explicame", "explícame", "como esta el negocio", "cómo está el negocio",
    "como va el negocio", "cómo va el negocio", "que tal va", "qué tal va",
)


def _detect_intent(text: str) -> str:
    """Returns 'chart', 'table', or 'question'."""
    low = text.lower()
    # "gráfica/barras/pastel..." gana siempre (aunque diga 'top'): 'top' pasa a
    # ser un límite dentro de la gráfica, no un cambio a tabla.
    if any(w in low for w in _STRONG_CHART_WORDS):
        return "chart"
    is_chart = any(w in low for w in _CHART_WORDS)
    is_table = any(w in low for w in _TABLE_WORDS)
    has_strong_table = any(w in low for w in _STRONG_TABLE_WORDS)
    if is_table and has_strong_table:
        return "table"
    # Preguntas de opinión/análisis en prosa ganan sobre una palabra de
    # gráfica/tabla "incidental" (p. ej. 'tendencia' en "qué opinas de la
    # tendencia del negocio" no debe forzar una gráfica vacía de texto).
    if any(w in low for w in _QUESTION_OVERRIDE_WORDS):
        return "question"
    if is_table and not is_chart:
        return "table"
    if is_chart:
        return "chart"
    return "question"


def _detect_chart_type(text: str) -> str:
    low = text.lower()
    for kw, tipo in _CHART_TYPE_MAP.items():
        if kw in low:
            return tipo
    return "barras"


def _normalize(s: str) -> str:
    """Lowercase, turn separators into spaces, collapse whitespace, drop accents."""
    s = str(s).lower().replace("_", " ").replace("-", " ")
    trans = str.maketrans("áéíóúü", "aeiouu")
    s = s.translate(trans)
    return re.sub(r"\s+", " ", s).strip()


# Sinónimos de negocio → posibles nombres de columna. La palabra a la izquierda
# (lo que escribe el usuario) mapea a la primera columna existente de la derecha.
_CONCEPTS = [
    (["ventas", "venta", "ingreso", "ingresos", "monto", "importe", "facturacion",
      "vendido", "vendidas", "vendidos", "revenue", "dinero", "ganamos", "ganancia",
      "ganancias", "ganado", "vendio", "vende", "venden", "facturado", "facturamos"],
     ["line_total", "total", "ventas", "venta", "monto", "importe", "subtotal", "revenue", "amount"]),
    (["producto", "productos", "item", "items", "articulo", "articulos", "sku",
      "objeto", "objetos", "mercancia", "mercancias", "cada uno"],
     ["producto", "product", "nombre", "name", "item", "articulo", "sku"]),
    (["unidad", "unidades", "cantidad", "cantidades", "piezas"],
     ["qty", "cantidad", "unidades", "quantity", "units"]),
    (["categoria", "categorias", "rubro", "rubros", "tipo de producto"],
     ["categoria", "category", "rubro"]),
    (["orden", "ordenes", "pedido", "pedidos", "compra", "compras"],
     ["orden", "order", "pedido", "order_number"]),
    (["estado", "estados", "status", "situacion"],
     ["estado_orden", "estado", "status"]),
    (["tipo", "tipos", "modalidad"],
     ["tipo_orden", "tipo", "type"]),
    (["cliente", "clientes", "comprador", "compradores", "usuario", "usuarios"],
     ["cliente", "customer", "comprador", "buyer", "user", "usuario"]),
    (["precio", "precios", "costo", "costos"],
     ["precio", "price", "unit_price", "unit_price_snapshot", "costo"]),
    (["fecha", "fechas", "dia", "dias", "mes", "meses", "año", "anio"],
     ["fecha", "date", "created_at", "creado", "dia", "mes", "año"]),
]


def _synonym_map(df: pd.DataFrame) -> dict:
    """{palabra_usuario: columna_real} para las columnas presentes en df."""
    cols = list(df.columns)
    normcol = {_normalize(c): c for c in cols}
    out: dict = {}
    for words, targets in _CONCEPTS:
        target = next((normcol[_normalize(t)] for t in targets if _normalize(t) in normcol), None)
        if not target:
            continue
        for w in words:
            out.setdefault(_normalize(w), target)
    return out


def _find_columns(text: str, df: pd.DataFrame) -> list[str]:
    """Return column names mentioned in text, ordered by position.

    1. Exact substring match on normalized forms ('nombre producto' → 'nombre_producto').
    2. Business synonyms ('item'→producto, 'ventas'→line_total, etc.).
    3. Fuzzy fallback for typos via difflib.
    """
    low = _normalize(text)
    norm_map = {col: _normalize(col) for col in df.columns}

    found: list[tuple[int, str]] = []
    matched: set[str] = set()
    for col, norm in norm_map.items():
        pos = low.find(norm)
        if pos >= 0:
            found.append((pos, col))
            matched.add(col)

    # Sinónimos de negocio (respetando la posición en el texto)
    for word, col in _synonym_map(df).items():
        if col in matched:
            continue
        m = re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", low)
        if m:
            found.append((m.start(), col))
            matched.add(col)

    found.sort()
    result = [col for _, col in found]

    remaining = [c for c in df.columns if c not in matched]
    if remaining:
        tokens = low.split()
        bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
        candidates = tokens + bigrams
        if candidates:
            for col in remaining:
                norm = norm_map[col]
                close = difflib.get_close_matches(norm, candidates, n=1, cutoff=0.82)
                if close:
                    result.append(col)
    return result


# ── Filtros en lenguaje natural ─────────────────────────────────────────────
_OP_PATTERNS = [
    (r">=|≥|mayor o igual (?:a|que)|al menos|por lo menos|minimo", ">="),
    (r"<=|≤|menor o igual (?:a|que)|como mucho|maximo", "<="),
    (r">|mayor(?:es)? (?:a|que|de)?|mas de|superior(?:es)? a|arriba de|por encima de", ">"),
    (r"<|menor(?:es)? (?:a|que|de)?|menos de|inferior(?:es)? a|debajo de|por debajo de", "<"),
    (r"!=|distinto[s]? (?:a|de)?|diferente[s]? (?:a|de)?|que no (?:sea|son)", "!="),
    (r"==|=|igual(?:es)? (?:a|que)?|exactamente", "=="),
]


def _detect_filters(text: str, df: pd.DataFrame) -> dict:
    """Detect natural-language filters like 'donde precio > 100' or
    'solo región Norte'. Returns {col: {op, val}} | {col: value}."""
    low = _normalize(text)
    filtros: dict = {}

    # Numeric comparisons: <column> <operator> <number>
    for col in df.select_dtypes(include="number").columns:
        norm = _normalize(col)
        for pat, op in _OP_PATTERNS:
            m = re.search(
                rf"{re.escape(norm)}\s*(?:{pat})\s*(-?\d+(?:[.,]\d+)?)", low
            )
            if m:
                filtros[col] = {"op": op, "val": float(m.group(1).replace(",", "."))}
                break

    # Categorical equality: an actual category value appears in the text
    for col in df.columns:
        if col in filtros:
            continue
        dtype = df[col].dtype
        if (pd.api.types.is_numeric_dtype(dtype)
                or pd.api.types.is_bool_dtype(dtype)
                or pd.api.types.is_datetime64_any_dtype(dtype)):
            continue
        try:
            uniques = df[col].dropna().astype(str).unique()
        except Exception:
            continue
        if len(uniques) == 0 or len(uniques) > 100:
            continue
        # 1) valor completo aparece en el texto ("región Norte")
        matched = False
        for val in uniques:
            nval = _normalize(val)
            if len(nval) < 3:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(nval)}(?![a-z0-9])", low):
                filtros[col] = str(val)
                matched = True
                break
        if matched:
            continue
        # 2) coincidencia parcial: una palabra distintiva del valor aparece en el
        #    texto ("gaming" → "Gaming & Peripherals"). Solo palabras de ≥4 letras
        #    y únicas a un valor, para evitar falsos positivos.
        word_to_val: dict = {}
        for val in uniques:
            for w in re.findall(r"[a-z0-9]{4,}", _normalize(val)):
                word_to_val.setdefault(w, set()).add(str(val))
        low_tokens = re.findall(r"[a-z0-9]{4,}", low)
        for w, vals in word_to_val.items():
            if len(vals) != 1:
                continue  # palabra ambigua (en varios valores) → ignorar
            hit = bool(re.search(rf"(?<![a-z0-9]){w}(?![a-z0-9])", low))
            if not hit:
                # raíz compartida: "electronica" (texto, ES) ↔ "electronics"
                # (valor, EN). Prefijo común largo → mismo concepto.
                for t in low_tokens:
                    common = os.path.commonprefix([t, w])
                    # raíz de ≥6 letras que cubre ≥60% de la palabra más corta:
                    # "cancelados"(ES) ↔ "cancelled"(EN) comparten "cancel".
                    if len(common) >= 6 and len(common) >= 0.6 * min(len(t), len(w)):
                        hit = True
                        break
            if hit:
                filtros[col] = next(iter(vals))
                break

    return filtros


def _apply_filters(df: pd.DataFrame, filtros: dict | None) -> pd.DataFrame:
    """Apply a filter dict to a DataFrame (used by chart and table builders)."""
    result = df
    for col, val in (filtros or {}).items():
        if col not in result.columns:
            continue
        try:
            if isinstance(val, dict):
                ops = {">": "__gt__", "<": "__lt__", ">=": "__ge__",
                       "<=": "__le__", "==": "__eq__", "!=": "__ne__"}
                fn = ops.get(val.get("op", "=="), "__eq__")
                result = result[getattr(result[col], fn)(val["val"])]
            else:
                result = result[result[col].astype(str).str.lower() == str(val).lower()]
        except Exception:
            continue
    return result


def _cat_columns(df: pd.DataFrame) -> list[str]:
    """Categóricas para graficar: no numéricas, no fecha, cardinalidad razonable."""
    out = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            continue
        try:
            nun = s.nunique(dropna=True)
        except TypeError:
            continue
        if 0 < nun <= 50:
            out.append(c)
    return out


_METRIC_HINTS = ("line_total", "total", "ventas", "venta", "monto", "importe",
                 "subtotal", "revenue", "ingreso", "amount", "precio")


def _primary_metric(num_all: list) -> str | None:
    """La columna numérica que representa 'dinero/ventas' (para que 'por producto'
    sea, por defecto, cuánto vendió cada uno — no la frecuencia)."""
    norm = {c: _normalize(c) for c in num_all}
    for hint in _METRIC_HINTS:
        for c in num_all:
            if norm[c] == hint:
                return c
    for hint in _METRIC_HINTS:
        for c in num_all:
            if hint in norm[c]:
                return c
    return None


# Columnas que representan el "ítem" que se rankea (producto, cliente, etc.).
# Se prefieren aunque sean de alta cardinalidad: un "top N más vendidos" es un
# ranking de PRODUCTOS, no de categorías.
_DIMENSION_HINTS = ("producto", "product", "articulo", "mercancia", "item",
                    "sku", "nombre", "name", "cliente", "customer", "titulo", "title")


def _primary_dimension(df: pd.DataFrame) -> str | None:
    """La columna de 'ítem' para rankear (producto/cliente/…). A diferencia de
    _cat_columns, NO descarta por cardinalidad alta: 'top 10 más vendidos' rankea
    productos individuales, no la categoría que los agrupa."""
    text_cols = [c for c in df.columns
                 if not pd.api.types.is_numeric_dtype(df[c])
                 and not pd.api.types.is_datetime64_any_dtype(df[c])]
    norm = {c: _normalize(c) for c in text_cols}
    for hint in _DIMENSION_HINTS:            # 1) por nombre exacto
        for c in text_cols:
            if norm[c] == hint:
                return c
    for hint in _DIMENSION_HINTS:            # 2) por nombre parcial
        for c in text_cols:
            if hint in norm[c]:
                return c
    # 3) sin pistas de nombre: la textual con más variedad, pero no un id único
    #    por fila (excluye columnas casi-únicas tipo order_number).
    best, best_nun = None, 0
    n = max(len(df), 1)
    for c in text_cols:
        try:
            nun = df[c].nunique(dropna=True)
        except TypeError:
            continue
        if nun / n > 0.9:      # casi un valor distinto por fila → es un id, no un ítem
            continue
        if nun > best_nun:
            best, best_nun = c, nun
    return best


def _detect_agg(low: str) -> str:
    # Con límites de palabra: evita que 'min' matchee dentro de 'gaMINg', etc.
    def has(*words):
        return any(re.search(rf"(?<![a-z0-9]){w}(?![a-z0-9])", low) for w in words)
    if has("promedio", "media", "mean", "average"):
        return "mean"
    if has("maximo", "máximo", "max"):
        return "max"
    if has("minimo", "mínimo", "min"):
        return "min"
    if has("conteo", "cuantos", "cuántos", "frecuencia", "numero de"):
        return "count"
    return "sum"


def _resolve_chart_shape(user_msg: str, df: pd.DataFrame) -> dict:
    """Extrae *qué* se pide, independiente del tipo de gráfica: dimensión (por qué
    desglosar), métrica (qué medir), agregación, límite y una 2ª dimensión. Todos
    los tipos consumen esta misma resolución, así 'top 10 más vendidos', 'pastel
    según las ventas' y 'treemap por categoría' eligen dimensión/métrica igual —
    no hay reglas distintas escondidas en cada tipo."""
    low = user_msg.lower()
    mentioned = _find_columns(user_msg, df)
    num_all  = list(df.select_dtypes(include="number").columns)
    date_all = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
    cat_all  = _cat_columns(df)
    men_num  = [c for c in mentioned if c in num_all]
    # Dimensiones nombradas (categóricas O texto de alta cardinalidad como
    # 'producto', pero no fechas): si el usuario la nombra, manda.
    men_dims = [c for c in mentioned if c not in num_all and c not in date_all]

    agg = _detect_agg(low)
    tm = re.search(r"top\s*(\d+)|(?:los|las)\s+(\d+)\s+m[aá]s", low)
    top_n = int(tm.group(1) or tm.group(2)) if tm else None
    # Un "ranking" ("top N", "más vendidos"…) rankea ítems individuales.
    wants_ranking = bool(top_n) or bool(re.search(r"vendid|mejores|peores|ranking", low))

    # Dimensión de AGRUPACIÓN explícita: "…por X", "…según X", "agrupado por X",
    # "desglosa por/según X". Lo que va DESPUÉS de la preposición es la dimensión
    # real — no el 1er sustantivo. Así "productos según su estado de orden" agrupa
    # por estado, y "desglosa las órdenes canceladas según el producto" por producto.
    grp_dim = None
    mgrp = re.search(r"\b(?:seg[uú]n|por|agrupad[oa]s?\s+por|desglos\w*\s+(?:por|seg[uú]n)|"
                     r"de acuerdo a|en funci[oó]n de)\b", low)
    if mgrp:
        tail = user_msg[mgrp.end():]
        grp_dim = next((c for c in _find_columns(tail, df)
                        if c not in num_all and c not in date_all), None)

    # Dimensión: agrupación explícita > nombrada > (ranking → ítem) > categórica
    if grp_dim:
        dim = grp_dim
    elif men_dims:
        dim = men_dims[0]
    elif wants_ranking:
        dim = _primary_dimension(df) or (cat_all[0] if cat_all else None)
    else:
        dim = cat_all[0] if cat_all else _primary_dimension(df)
    # 2ª dimensión (para color / jerarquía en treemap-sunburst)
    dim2 = next(iter(men_dims[1:]), None) or next((c for c in cat_all if c != dim), None)

    return {
        "low": low, "cat_all": cat_all, "num_all": num_all, "date_all": date_all,
        "men_num": men_num, "men_dims": men_dims,
        "agg": agg, "wants_count": agg == "count", "wants_ranking": wants_ranking,
        "top_n": top_n, "dim": dim, "dim2": dim2,
        "metric_named": men_num[0] if men_num else None,
        "metric_default": _primary_metric(num_all) or (num_all[0] if num_all else None),
    }


def _fast_chart_spec(user_msg: str, df: pd.DataFrame) -> dict:
    """Construye el spec: primero resuelve la 'forma' semántica (dimensión,
    métrica, agregación, límite) y luego el tipo de gráfica solo coloca esos
    componentes — el tipo es *cómo* se dibuja, no *qué* se muestra."""
    s = _resolve_chart_shape(user_msg, df)
    tipo = _detect_chart_type(user_msg)
    dim, dim2   = s["dim"], s["dim2"]
    metric      = s["metric_named"] or s["metric_default"]   # valor a medir
    metric_only = s["metric_named"]                          # solo si lo nombró

    spec: dict = {"tipo": tipo}
    if s["top_n"]:
        spec["top_n"] = s["top_n"]

    if tipo == "correlacion":
        return spec

    if tipo in ("histograma", "boxplot"):
        spec["x"] = metric or (_find_columns(user_msg, df) or [None])[0]
        if tipo == "boxplot" and dim:
            spec["color"] = dim
        return spec

    if tipo == "dispersion":
        nums = s["men_num"] if len(s["men_num"]) >= 2 else s["num_all"]
        if len(nums) >= 2:
            spec["x"], spec["y"] = nums[0], nums[1]
        if dim:
            spec["color"] = dim
        return spec

    if tipo in ("treemap", "sunburst"):
        if dim:
            spec["x"] = dim
        if dim2:
            spec["color"] = dim2
        spec["y"] = metric
        return spec

    if tipo == "funnel":
        spec["x"] = dim
        spec["y"] = metric
        return spec

    if tipo == "gauge":
        spec["y"] = metric
        return spec

    if tipo == "linea":
        spec["x"] = (s["date_all"][0] if s["date_all"] else
                     (dim or (df.columns[0] if len(df.columns) else None)))
        spec["y"] = metric
        return spec

    if tipo == "pastel":
        spec["x"] = dim
        # Se pondera por la métrica NOMBRADA ("según las ventas"); si no se nombró
        # ninguna, el pastel muestra proporción por frecuencia (conteo de filas).
        if metric_only and not s["wants_count"]:
            spec["y"] = metric_only
            spec["agregar"] = s["agg"] if s["agg"] != "count" else "sum"
        return spec

    # ── barras ──
    if dim and metric and not s["wants_count"]:
        spec["tipo"] = "barras_agrupadas"
        spec["x"] = dim
        spec["y"] = metric
        spec["agrupar_por"] = dim
        spec["agregar"] = s["agg"]
    elif dim:
        spec["x"] = dim            # bar_top: frecuencia / conteo de valores
    elif metric:
        spec["tipo"] = "histograma"  # solo numérica → distribución
        spec["x"] = metric
    return spec


def _fast_table_spec(user_msg: str, df: pd.DataFrame) -> dict:
    low = user_msg.lower()
    all_mentioned = _find_columns(user_msg, df)
    num_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = [c for c in df.columns if df[c].dtype == object or df[c].nunique() < 30]
    mentioned_num = [c for c in all_mentioned if c in num_cols]
    mentioned_cat = [c for c in all_mentioned if c in cat_cols and c not in num_cols]

    top_match = re.search(r"top\s*(\d+)", low)
    top_n = int(top_match.group(1)) if top_match else None

    if any(w in low for w in ("estadísticas", "estadisticas", "resumen", "describe")):
        return {"operacion": "describe"}

    if any(w in low for w in ("frecuencia", "conteo", "cuántos", "cuantos")):
        col = mentioned_cat[0] if mentioned_cat else (cat_cols[0] if cat_cols else None)
        return {"operacion": "value_counts", "columnas": [col] if col else []}

    if any(w in low for w in ("agrupa", "agrúpa", "suma por", "promedio por", "agrupar")):
        by = mentioned_cat or (cat_cols[:1] if cat_cols else [])
        agg_col = mentioned_num[0] if mentioned_num else (num_cols[0] if num_cols else None)
        fn = "mean" if "promedio" in low else "sum" if "suma" in low else "count"
        spec: dict = {"operacion": "groupby", "agrupar_por": by}
        if agg_col:
            spec["agregar"] = {agg_col: fn}
            spec["ordenar_por"] = agg_col
        if top_n:
            spec["top_n"] = top_n
        return spec

    # Default: sort by numeric column, limit if top N requested
    sort_col = mentioned_num[0] if mentioned_num else (num_cols[0] if num_cols else None)
    spec = {"operacion": "sort"}
    if sort_col:
        spec["ordenar_por"] = sort_col
    if top_n:
        spec["top_n"] = top_n
    if all_mentioned:
        spec["columnas"] = all_mentioned
    return spec


def _fmt(v) -> str:
    try:
        if isinstance(v, float):
            return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"
        if isinstance(v, (int,)):
            return f"{v:,}"
    except Exception:
        pass
    return str(v)


def _answer_question_offline(df: pd.DataFrame, msg: str) -> str | None:
    """Responde preguntas analíticas comunes con pandas (instantáneo, sin LLM ni
    tokens). Devuelve None si no la puede contestar (entonces se usa el LLM)."""
    low = _normalize(msg)
    mentioned = _find_columns(msg, df)
    num_all = list(df.select_dtypes(include="number").columns)
    cat_all = _cat_columns(df)
    men_num = [c for c in mentioned if c in num_all]
    men_cat = [c for c in mentioned if c in cat_all]
    # Texto mencionado, incluida alta cardinalidad ('producto') que cat_all excluye
    men_txt = [c for c in mentioned if c not in num_all]

    # "cuántos/cuántas" (plural) = CONTEO; "cuánto/cuánta" (singular) = MONTO ($).
    is_count = bool(re.search(r"\bcuant[ao]s\b", low)) or "cantidad de" in low or "numero de" in low
    is_amount = bool(re.search(r"\bcuant[ao]\b", low)) or any(
        w in low for w in ("se perdio", "perdida", "perdido", "perdimos", "se gano",
                           "ganamos", "ganancia", "se vendio", "vendimos", "ingreso",
                           "factur", "cuanto vale", "monto"))
    sup_max = any(w in low for w in ("mas ", "mayor", "mejor", "top", "maximo", "alto", "vende mas"))
    sup_min = any(w in low for w in ("menos", "menor", "peor", "minimo", "bajo"))
    agg_words = is_amount or any(w in low for w in ("promedio", "media", "total", "suma",
                                                    "maximo", "minimo", "mean", "average"))

    # 0) Filtro ("ventas solo en el oeste", "total donde region = norte"):
    #    se calcula al instante sobre los datos filtrados, sin LLM.
    filtros = _detect_filters(msg, df)
    if filtros and not (sup_max or sup_min):
        sub = _apply_filters(df, filtros)
        desc = ", ".join(
            f"{L.pretty(k)} {v['op']} {_fmt(v['val'])}" if isinstance(v, dict)
            else f"{L.pretty(k)} = {v}"
            for k, v in filtros.items())
        if sub.empty:
            return f"No hay filas que cumplan {desc}."
        # Métrica: la nombrada, o la de dinero por defecto si preguntan un MONTO
        # ("cuánto se perdió con los cancelados" → suma line_total del subconjunto).
        num = men_num[0] if men_num else None
        if num is None and (is_amount or agg_words):
            num = _primary_metric(num_all) or (num_all[0] if num_all else None)
        if num:
            agg = _detect_agg(low)
            agg = "sum" if agg == "count" else agg
            etiqueta = {"mean": "promedio", "sum": "total", "max": "máximo", "min": "mínimo"}[agg]
            val = getattr(sub[num], agg)()
            return (f"El {etiqueta} de {L.pretty(num)} para {desc} es {_fmt(val)} "
                    f"(sobre {len(sub):,} de {len(df):,} filas).")
        return f"Hay {len(sub):,} filas que cumplen {desc} (de {len(df):,})."

    # 1) Conteo de filas
    if is_count and not men_cat and not men_num and any(
            w in low for w in ("registro", "fila", "dato", "row", "hay en total", "total de")):
        return f"El conjunto tiene {len(df):,} filas y {df.shape[1]} columnas."

    # 2) Valores distintos de una categórica o texto (incl. 'producto', de alta
    #    cardinalidad, que no está en cat_all)
    if (is_count or "distint" in low) and men_txt:
        c = men_txt[0]
        return f"Hay {df[c].nunique(dropna=True):,} valores distintos en «{L.pretty(c)}»."

    # 3) Superlativo: ¿cuál <cat> tiene más/menos <num>?  (usa men_txt para incluir
    #    'producto' de alta cardinalidad; la métrica cae en la de dinero si no se
    #    nombra: "¿cuál producto vende más?" → total de line_total por producto)
    if (sup_max or sup_min) and men_txt and (men_num or num_all):
        cat = men_txt[0]
        num = men_num[0] if men_num else (_primary_metric(num_all) or num_all[0])
        agg = _detect_agg(low)
        agg = "sum" if agg == "count" else agg
        ascending = sup_min and not sup_max
        try:
            g = df.groupby(cat)[num].agg(agg).sort_values(ascending=ascending)
            if not g.empty:
                cual = "menor" if ascending else "mayor"
                etiqueta = {"mean": "promedio", "sum": "total", "max": "máximo", "min": "mínimo"}.get(agg, agg)
                return (f"«{g.index[0]}» tiene el {cual} {etiqueta} de {L.pretty(num)}: "
                        f"{_fmt(g.iloc[0])}. (Siguiente: «{g.index[1]}» {_fmt(g.iloc[1])}.)"
                        if len(g) > 1 else
                        f"«{g.index[0]}» tiene el {cual} {etiqueta} de {L.pretty(num)}: {_fmt(g.iloc[0])}.")
        except Exception:
            return None

    # 4) Agregado de un numérico (promedio/total/máx/mín), opcional por categórica
    if men_num and (agg_words or is_count):
        num = men_num[0]
        agg = _detect_agg(low)
        agg = "mean" if agg == "count" else agg
        etiqueta = {"mean": "promedio", "sum": "total", "max": "máximo", "min": "mínimo"}[agg]
        try:
            if men_cat:
                cat = men_cat[0]
                g = df.groupby(cat)[num].agg(agg).sort_values(ascending=False).head(5)
                detalle = "; ".join(f"{i}: {_fmt(v)}" for i, v in g.items())
                return f"{etiqueta.capitalize()} de {L.pretty(num)} por {L.pretty(cat)} (top 5) — {detalle}."
            return f"El {etiqueta} de {L.pretty(num)} es {_fmt(getattr(df[num], agg)())}."
        except Exception:
            return None

    # 4b) Monto sin numérico nombrado: "cuánto se vendió/perdió" → suma la
    #     métrica de dinero por defecto, opcionalmente por categoría.
    if (is_amount or agg_words) and not men_num and num_all:
        num = _primary_metric(num_all) or num_all[0]
        agg = _detect_agg(low)
        agg = "sum" if agg == "count" else agg
        etiqueta = {"mean": "promedio", "sum": "total", "max": "máximo", "min": "mínimo"}[agg]
        try:
            if men_cat:
                cat = men_cat[0]
                g = df.groupby(cat)[num].agg(agg).sort_values(ascending=False).head(5)
                detalle = "; ".join(f"{i}: {_fmt(v)}" for i, v in g.items())
                return f"{etiqueta.capitalize()} de {L.pretty(num)} por {L.pretty(cat)} (top 5) — {detalle}."
            return f"El {etiqueta} de {L.pretty(num)} es {_fmt(getattr(df[num], agg)())}."
        except Exception:
            return None

    # 5) Resumen general del dataset
    if any(w in low for w in ("resumen", "resume", "describe", "overview", "de que trata",
                              "que contiene", "que hay", "que datos")):
        parts = [f"{len(df):,} filas × {df.shape[1]} columnas"]
        if num_all:
            try:
                c = df[num_all].std(numeric_only=True).idxmax()
                parts.append(f"{len(num_all)} numéricas (mayor variación en «{L.pretty(c)}»)")
            except Exception:
                parts.append(f"{len(num_all)} numéricas")
        if cat_all:
            parts.append(f"{len(cat_all)} categóricas (ej. {', '.join(L.pretty(c) for c in cat_all[:3])})")
        nulls = int(df.isnull().sum().sum())
        parts.append(f"{nulls:,} valores nulos" if nulls else "sin nulos")
        return "El dataset tiene " + "; ".join(parts) + "."

    return None


def _build_context(df: pd.DataFrame, max_rows: int = 10) -> str:
    lines = [f"Dataset: {df.shape[0]} filas × {df.shape[1]} columnas\n\nColumnas "
             "(usa el nombre real solo para llamar herramientas/filtros; al "
             "escribirle al usuario, referite a la columna por su etiqueta):"]
    for col in df.columns:
        sample_vals = list(df[col].dropna().unique()[:3])
        lines.append(f'  - "{col}" (etiqueta: "{L.pretty(col)}", tipo: {df[col].dtype}) '
                     f'ejemplos: {sample_vals}')
    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        stats = numeric.agg(["mean", "min", "max"]).round(2)
        lines.append("\nEstadísticas (mean/min/max):")
        lines.append(stats.to_string())
    lines.append(f"\nMuestra ({min(max_rows, len(df))} filas):")
    sample = df.head(max_rows).copy()
    for col in sample.select_dtypes(include=["datetime", "datetimetz"]).columns:
        sample[col] = sample[col].astype(str)
    lines.append(sample.to_json(orient="records", force_ascii=False, default_handler=str))
    return "\n".join(lines)


# ── Chart builder ──────────────────────────────────────────────────────────
def build_chart_from_spec(df: pd.DataFrame, spec: dict):
    tipo     = spec.get("tipo", "barras")
    x        = spec.get("x")
    y        = spec.get("y")
    color    = spec.get("color")
    agrupar  = spec.get("agrupar_por") or x
    agregar  = spec.get("agregar", "sum")
    top_n    = int(spec.get("top_n") or 15)
    titulo   = spec.get("titulo", "")

    df = _apply_filters(df, spec.get("filtros"))
    if df.empty:
        return None

    cols     = list(df.columns)
    num_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = [c for c in cols if df[c].dtype == object or df[c].nunique() < 30]

    def valid(c):
        return c if c and c in cols else None

    x, y, color, agrupar = valid(x), valid(y), valid(color), valid(agrupar)

    try:
        if tipo == "histograma":
            col = x or (num_cols[0] if num_cols else None)
            fig = cg.histogram(df, col) if col else None

        elif tipo == "barras":
            col = x or (cat_cols[0] if cat_cols else None)
            fig = cg.bar_top(df, col, top_n) if col else None

        elif tipo == "pastel":
            col = x or (cat_cols[0] if cat_cols else None)
            val = y if y in num_cols else None   # ponderar por métrica si se dio
            fig = cg.pie_chart(df, col, top_n, val, agregar) if col else None

        elif tipo == "dispersion":
            xc = x or (num_cols[0] if len(num_cols) > 1 else None)
            yc = y or (num_cols[1] if len(num_cols) > 1 else None)
            fig = cg.scatter(df, xc, yc, color) if xc and yc else None

        elif tipo == "linea":
            xc = x or cols[0]
            yc = y or (num_cols[0] if num_cols else None)
            fig = cg.line_chart(df, xc, yc) if xc and yc else None

        elif tipo == "boxplot":
            col = y or x or (num_cols[0] if num_cols else None)
            grp = color or agrupar
            if grp and df[grp].nunique() > 15:
                grp = None
            fig = cg.box_plot(df, col, grp) if col else None

        elif tipo == "barras_agrupadas":
            grp = agrupar or x or (cat_cols[0] if cat_cols else None)
            val = y or (num_cols[0] if num_cols else None)
            fig = cg.grouped_bar(df, grp, val, agregar, top_n) if grp and val else None

        elif tipo == "correlacion":
            fig = cg.correlation_heatmap(df) if len(num_cols) >= 2 else None

        elif tipo in ("treemap", "sunburst"):
            path = [c for c in (x, color, agrupar) if c and c in cat_cols]
            path = list(dict.fromkeys(path))[:3]
            if not path:
                path = cat_cols[:2]
            val = y or (num_cols[0] if num_cols else None)
            builder = cg.treemap if tipo == "treemap" else cg.sunburst
            fig = builder(df, path, val) if path else None

        elif tipo == "funnel":
            stage = x or (cat_cols[0] if cat_cols else None)
            val = y or (num_cols[0] if num_cols else None)
            fig = cg.funnel(df, stage, val) if stage else None

        elif tipo == "gauge":
            col = y or (x if x in num_cols else None) or (num_cols[0] if num_cols else None)
            fig = cg.gauge(float(df[col].sum()), f"Total — {L.pretty(col)}") if col else None

        else:
            fig = None

        if fig and titulo:
            fig.update_layout(title=dict(text=f"<b>{titulo}</b>"))
        return fig

    except Exception:
        return None


# ── Table builder ──────────────────────────────────────────────────────────
def build_table_from_spec(df: pd.DataFrame, spec: dict) -> pd.DataFrame | None:
    try:
        op     = spec.get("operacion", "sort")
        result = _apply_filters(df.copy(), spec.get("filtros"))

        if op == "groupby":
            by  = spec.get("agrupar_por") or []
            agg = spec.get("agregar") or {}
            if by and agg:
                result = result.groupby(by).agg(agg).reset_index()

        elif op == "describe":
            cols = spec.get("columnas") or list(result.select_dtypes(include="number").columns)
            result = (result[cols].describe().round(3)
                      .reset_index().rename(columns={"index": "estadística"}))

        elif op == "value_counts":
            col = (spec.get("columnas") or [None])[0]
            if col and col in result.columns:
                vc = result[col].value_counts().reset_index()
                vc.columns = [col, "frecuencia"]
                result = vc

        elif op == "pivot":
            idx     = (spec.get("agrupar_por") or [None])[0]
            col2    = spec.get("col2")
            agg_d   = spec.get("agregar") or {}
            val_col = list(agg_d.keys())[0] if agg_d else None
            agg_fn  = list(agg_d.values())[0] if agg_d else "sum"
            if idx and col2 and val_col:
                result = (pd.pivot_table(result, index=idx, columns=col2,
                                         values=val_col, aggfunc=agg_fn, fill_value=0)
                          .reset_index())
                result.columns = [str(c) for c in result.columns]

        elif op == "crosstab":
            c1, c2 = spec.get("col1"), spec.get("col2")
            if c1 and c2 and c1 in df.columns and c2 in df.columns:
                result = pd.crosstab(df[c1], df[c2],
                                     margins=True, margins_name="TOTAL").reset_index()

        # Select columns
        cols_sel = spec.get("columnas")
        if cols_sel and op not in ("describe", "value_counts", "pivot", "crosstab"):
            existing = [c for c in cols_sel if c in result.columns]
            if existing:
                result = result[existing]

        # Sort
        sort_col = spec.get("ordenar_por")
        if sort_col and sort_col in result.columns:
            result = result.sort_values(sort_col, ascending=bool(spec.get("ascendente", False)))

        # Limit
        top_n = spec.get("top_n")
        if top_n:
            result = result.head(int(top_n))

        return result.reset_index(drop=True)

    except Exception:
        return None


# ── Public API ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def _client(api_key: str = "") -> OpenAI:
    return OpenAI(
        base_url=_base_url(),
        api_key=_llm_api_key(api_key),
        timeout=30.0,      # NIM 70B local: 30s por intento (nunca colgar)
        max_retries=0,     # sin reintentos internos (ya iteramos modelos)
    )


def _complete(api_key: str, messages: list, max_tokens: int = 300) -> str:
    """Texto del LLM con fallback robusto: prueba TODOS los modelos en orden y
    salta el que falle (404/429/etc.) o devuelva vacío."""
    client = _client(api_key)
    last_err = None
    for model in _models():   # normalmente 1 (el del contenedor); N si hay override
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content and _looks_like_reasoning(content):
                last_err = RuntimeError(f"{model} filtró razonamiento interno")
                continue  # respuesta con 'pensamiento' crudo → probar otro modelo
            if content:
                return content
            last_err = RuntimeError(f"{model} devolvió respuesta vacía")
        except Exception as e:
            last_err = e
        # cualquier fallo, vacío o razonamiento → siguiente modelo
    raise last_err or RuntimeError("Ningún modelo respondió")


def initial_analysis(df: pd.DataFrame, api_key: str = "") -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Analiza este dataset en 2 oraciones cortas.\n\n{_build_context(df, max_rows=5)}"
        )},
    ]
    try:
        return _complete(api_key, messages, max_tokens=150)
    except Exception as e:
        return f"⚠ Error IA: {e}"


def _recent_user_text(history: list[dict], n: int = 2) -> str:
    """Join the last `n` user messages — context for follow-up requests."""
    msgs = [m.get("content", "") for m in history
            if m.get("role") == "user" and m.get("content")]
    return " ".join(msgs[-n:])


def _prev_was_chart(history: list[dict]) -> bool:
    """True si la última respuesta del asistente fue una gráfica."""
    for m in reversed(history):
        if m.get("role") == "assistant":
            return bool(m.get("fig_spec"))
    return False


_CORRECTION_WORDS = ("sino", "si no", "en vez", "en lugar", "no la ", "no el ",
                     "no las ", "no los ", "mejor ", "cambia", "cambialo", "cámbialo")


def _after_connector(text: str) -> str:
    """Devuelve el texto tras un conector de corrección ('...sino Y' → 'Y').
    Así 'no la categoría sino los items' se enfoca en 'los items'."""
    low = text.lower()
    best = 0
    for c in ("sino", "si no", "en vez de", "en lugar de", "en vez", "en lugar"):
        j = low.rfind(c)
        if j >= 0:
            best = max(best, j + len(c))
    return text[best:].strip() if best else text


# ── Proyecciones a futuro ───────────────────────────────────────────────────
# (keywords ya sin acentos: _normalize los quita)
_FORECAST_WORDS = ("proyec", "pronostic", "forecast", "futuro", "proxim",
                   "estimacion", "estimar", "prevision", "preve", "crecimiento",
                   "crecer", "creciendo", "crecera", "expansion", "escenario",
                   "que esperar", "cuanto vendere", "cuanto vamos", "a la larga")
_DECLINE_WORDS = ("bajando", "declive", "cayendo", "caida", "disminuy", "decrecen",
                  "decreciendo", "a la baja", "perdiendo venta", "menos venta",
                  "bajan", "van mal", "peor tendencia", "en picada")
_RISE_WORDS = ("subiendo", "en alza", "al alza", "despegando", "ganando terreno",
               "mejor tendencia", "suben", "mas populares cada", "van mejor",
               "creciente", "mas demanda")


def _is_forecast(text: str) -> bool:
    low = _normalize(text)
    return any(w in low for w in _FORECAST_WORDS + _DECLINE_WORDS + _RISE_WORDS)


def _forecast_reply(df: pd.DataFrame, user_message: str, filtros: dict | None = None
                    ) -> tuple[str, object | None, pd.DataFrame | None]:
    """Proyección de una métrica a futuro, o ranking de productos que suben/bajan.
    Devuelve (texto, fig, tabla) — texto None si no aplica."""
    low = _normalize(user_message)
    date_col = forecasting.find_date_column(df)
    if not date_col:
        return ("Para proyectar a futuro necesito una columna de fecha (p. ej. la "
                "«fecha» de las órdenes). Con ella estimo ventas futuras, crecimiento "
                "y qué productos suben o bajan.", None, None)

    filtros = filtros or _detect_filters(user_message, df)
    data = _apply_filters(df, filtros) if filtros else df
    num_all = list(data.select_dtypes(include="number").columns)
    men_num = [c for c in _find_columns(user_message, df) if c in num_all]
    metric = men_num[0] if men_num else _primary_metric(num_all)

    freq, periods = forecasting.parse_horizon(low)
    if freq is None:
        freq = forecasting.auto_freq(data, date_col)
        periods = forecasting.default_horizon(freq)

    # 1) Productos que suben / bajan sus ventas
    declining = any(w in low for w in _DECLINE_WORDS)
    rising = (not declining) and any(w in low for w in _RISE_WORDS)
    if declining or rising:
        item_col = _primary_dimension(data)
        if not item_col:
            return ("No identifico una columna de producto/ítem para ver cuáles suben "
                    "o bajan.", None, None)
        trends = forecasting.item_trends(data, item_col, date_col, metric, freq=freq)
        if trends is None or trends.empty:
            return ("No hay suficiente historia por producto (necesito ≥3 períodos con "
                    "fecha) para separar los que suben de los que bajan.", None, None)
        fig = cg.trend_bar(trends, item_col, n=10, declining=declining)
        txt = forecasting.trends_summary(trends, item_col, rising=rising, label=L.pretty(metric))
        return txt, fig, None

    # 2) Proyección general de la métrica (crecimiento / ventas futuras)
    ts = forecasting.build_series(data, date_col, metric, freq=freq, agg="sum")
    result = forecasting.linear_forecast(ts, periods) if ts is not None else None
    if not result:
        return ("Aún no hay suficientes períodos con fecha para proyectar de forma "
                "fiable (necesito al menos 3). Prueba con un rango de fechas más amplio.",
                None, None)
    label = L.pretty(metric) if metric else "órdenes"
    fig = cg.forecast_chart(result, title=f"Proyección de {label}", y_title=str(label))
    txt = forecasting.forecast_summary(result, label, freq, periods, filtros)
    return txt, fig, None


def chat(
    df: pd.DataFrame,
    history: list[dict],
    user_message: str,
    api_key: str = "",
) -> tuple[str, object | None, pd.DataFrame | None]:
    """Returns (text, plotly_fig | None, dataframe | None).

    Hybrid routing:
      1. Keyword detection builds charts/tables instantly (no tokens, no latency).
      2. Natural-language filters ('donde precio > 100', 'solo región Norte')
         are detected and applied to the fast path.
      3. Follow-ups inherit context: if the current message names no columns,
         the previous user message's columns/filters are reused ('ahora en
         pastel', 'y por categoría').
      4. If the fast path can't build a result, the LLM with function-calling
         is used as a fallback (when an API key is available).
      5. Open questions go straight to the LLM (with recent history).
    """
    # Proyección a futuro (crecimiento, ventas futuras, productos que suben/bajan):
    # tiene su propio motor y gana antes del ruteo normal de gráfica/tabla, porque
    # "proyecta las ventas" también contiene palabras de gráfica/métrica.
    if _is_forecast(user_message):
        f_txt, f_fig, f_tab = _forecast_reply(df, user_message)
        if f_fig is not None or f_tab is not None or f_txt:
            return f_txt, f_fig, f_tab

    intent   = _detect_intent(user_message)
    filtros  = _detect_filters(user_message, df)
    prev_txt = _recent_user_text(history)
    mentioned_now = _find_columns(user_message, df)
    num_cols = set(df.select_dtypes(include="number").columns)
    # Hereda el contexto anterior cuando el mensaje actual no aporta una
    # DIMENSIÓN nueva (aunque nombre una métrica): "esa misma gráfica con el
    # top 5 más vendidos" solo dice la métrica → reusa 'producto' y el filtro
    # 'gaming' de la gráfica anterior.
    has_dim = any(c not in num_cols for c in mentioned_now)
    spec_text = f"{prev_txt} {user_message}" if (prev_txt and not has_dim) else user_message
    # El FILTRO ('solo electronica') es estado de la vista: persiste en cualquier
    # follow-up de una gráfica que no traiga su propio filtro — aunque el mensaje
    # renombre la dimensión ("...de cada uno"). Va aparte de la herencia de texto.
    if not filtros and prev_txt and (not has_dim or _prev_was_chart(history)):
        filtros = _detect_filters(prev_txt, df)

    # Corrección de una gráfica previa ("no la categoría, sino los items",
    # "mejor por producto"): rehace la gráfica con la nueva dimensión, enfocando
    # en lo que va después del 'sino' y heredando los filtros anteriores.
    if intent != "chart" and _prev_was_chart(history) and \
            any(w in user_message.lower() for w in _CORRECTION_WORDS):
        focus = _after_connector(user_message)
        if _find_columns(focus, df):
            intent = "chart"
            spec_text = focus
            if not filtros:
                filtros = _detect_filters(user_message, df) or _detect_filters(prev_txt, df)

    if intent == "chart":
        spec = _fast_chart_spec(spec_text, df)
        # El TIPO del mensaje actual manda… salvo que "barras" (genérico) intente
        # degradar una decisión más rica: "barras de ventas por categoría" ya es
        # barras_agrupadas (totales), no un conteo de frecuencia.
        if any(kw in user_message.lower() for kw in _CHART_TYPE_MAP):
            forced = _detect_chart_type(user_message)
            if not (forced == "barras" and spec.get("tipo") == "barras_agrupadas"):
                spec["tipo"] = forced
        if filtros:
            spec["filtros"] = filtros
        fig = build_chart_from_spec(df, spec)
        if fig is not None:
            return "", fig, None
        return _llm_fallback(df, history, user_message, api_key)

    if intent == "table":
        spec = _fast_table_spec(spec_text, df)
        if filtros:
            spec["filtros"] = filtros
        table = build_table_from_spec(df, spec)
        if table is not None and not table.empty:
            return "", None, table
        return _llm_fallback(df, history, user_message, api_key)

    # Pregunta: primero intenta responder con pandas (instantáneo, sin tokens)
    offline = _answer_question_offline(df, user_message)
    if offline:
        return offline, None, None
    # Si no, respuesta de texto del LLM (sin function-calling: más confiable en
    # modelos gratuitos, que devuelven vacío cuando se les fuerza una herramienta).
    return _answer_with_llm(df, history, user_message, api_key), None, None


_NO_KEY_MSG = (
    "El modelo de IA está desactivado (LLM_OFFLINE). Aun así puedo darte gráficas "
    "y tablas al instante, y responder con números: «barras de <col>», «top 10 por "
    "<col>», «promedio de <col> por <col>», «¿cuál <categoría> tiene más <métrica>?»."
)


def _answer_with_llm(df: pd.DataFrame, history: list[dict],
                     user_message: str, api_key: str = "") -> str:
    if not _llm_enabled():
        return _NO_KEY_MSG
    context = _build_context(df, max_rows=8)
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nDATASET:\n{context}"}]
    for m in history[-6:]:
        c = m.get("content") or ""
        if not c:
            c = ("(gráfica generada)" if m.get("fig_spec")
                 else "(tabla generada)" if m.get("table") else "")
        if c:
            messages.append({"role": m["role"], "content": c})
    messages.append({"role": "user", "content": user_message})
    try:
        return _complete(api_key, messages, max_tokens=350)
    except Exception as e:
        return (f"⚠ No pude obtener respuesta del modelo ({str(e)[:80]}). "
                "Intenta de nuevo, o pídeme una gráfica/tabla o una pregunta con números.")


def _llm_fallback(
    df: pd.DataFrame,
    history: list[dict],
    user_message: str,
    api_key: str = "",
) -> tuple[str, object | None, pd.DataFrame | None]:
    """LLM with function-calling. Lets the model pick create_chart /
    create_table / answer_question. Degrades to plain text if the model
    doesn't support tools, and returns a friendly error on failure."""
    if not _llm_enabled():
        return (
            "El modelo de IA está desactivado (LLM_OFFLINE). Aun así puedo darte "
            "gráficas y tablas al instante: prueba «barras de <columna>», "
            "«top 10 por <columna>», «pastel por <columna>» o «estadísticas».",
            None, None,
        )

    context  = _build_context(df, max_rows=5)
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nDATASET:\n{context}"}]
    for msg in history[-6:]:
        content = msg.get("content") or ""
        if not content:  # turnos donde se generó una gráfica/tabla (texto vacío)
            if msg.get("fig_spec"):
                content = "(Generé una gráfica para la petición anterior.)"
            elif msg.get("table"):
                content = "(Generé una tabla para la petición anterior.)"
        if content:
            messages.append({"role": msg["role"], "content": content})
    messages.append({"role": "user", "content": user_message})

    client   = _client(api_key)
    last_err = None
    for model in _models():
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=400,
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments or "{}")
                name = call.function.name
                if name == "create_chart":
                    return args.get("comentario", ""), build_chart_from_spec(df, args), None
                if name == "create_table":
                    return args.get("comentario", ""), None, build_table_from_spec(df, args)
                return args.get("respuesta", "") or (msg.content or ""), None, None
            return msg.content or "", None, None
        except Exception as e:
            last_err = e
            if "429" in str(e) or "rate" in str(e).lower():
                continue  # try next free model
            break  # tools unsupported / other error → try plain text below

    # Plain-text fallback (no tools) if function-calling failed
    try:
        return _complete(api_key, messages, max_tokens=300), None, None
    except Exception as e:
        return f"⚠ Error IA: {last_err or e}", None, None


def suggest_tables(df: pd.DataFrame, api_key: str = "") -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"¿Qué análisis visuales y tablas serían más útiles? "
            f"Sé específico con nombres de columnas.\n\n{_build_context(df, max_rows=20)}"
        )},
    ]
    try:
        return _complete(api_key, messages, max_tokens=400)
    except Exception as e:
        return f"⚠ Error IA: {e}"
