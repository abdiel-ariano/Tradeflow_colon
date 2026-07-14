"""
Fuentes de datos para Analytics IA.

- Persistencia del DataFrame cargado entre requests, vía caché de Django,
  con clave por sesión (Streamlit guardaba esto en session_state).
- Carga directa desde los modelos ORM de Tradeflow (Order, Product, etc.)
  sin necesidad de exportar archivos.
"""
from __future__ import annotations
import pandas as pd
from django.apps import apps
from django.core.cache import cache

CACHE_PREFIX = "analytics:df:"
DB_PREFIX = "analytics:db:"
CACHE_TIMEOUT = 60 * 60  # 1 hora

# Modelos técnicos que no aporta nada analizar
_HIDE_MODELS = {"Session", "LogEntry", "AccessAttempt", "AccessLog",
                "AccessFailureLog", "ContentType", "Permission"}


def _sid(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return str(request.session.session_key)


def store_df(request, df: pd.DataFrame, meta: dict | None = None) -> None:
    cache.set(f"{CACHE_PREFIX}{_sid(request)}", {"df": df, "meta": meta or {}}, CACHE_TIMEOUT)


def get_df(request):
    payload = cache.get(f"{CACHE_PREFIX}{_sid(request)}")
    if not payload:
        return None, {}
    return payload["df"], payload.get("meta", {})


def clear_df(request) -> None:
    cache.delete(f"{CACHE_PREFIX}{_sid(request)}")


# ── Conexión a base de datos (Supabase/PostgreSQL) ──────────────────────────
def store_db(request, conn_str: str, tables: list, schema: str = "public",
             fks: list | None = None) -> None:
    cache.set(
        f"{DB_PREFIX}{_sid(request)}",
        {"conn": conn_str, "tables": tables, "schema": schema, "fks": fks or []},
        CACHE_TIMEOUT,
    )


def get_db(request):
    """Devuelve {'conn','tables','schema','fks'} o None."""
    return cache.get(f"{DB_PREFIX}{_sid(request)}")


def clear_db(request) -> None:
    cache.delete(f"{DB_PREFIX}{_sid(request)}")


# ── Excel multi-hoja: recordar el archivo para cambiar de hoja sin re-subir ──
XLSX_PREFIX = "analytics:xlsx:"


def store_excel(request, data: bytes, sheets: list, current: str) -> None:
    cache.set(f"{XLSX_PREFIX}{_sid(request)}",
              {"bytes": data, "sheets": sheets, "current": current}, CACHE_TIMEOUT)


def get_excel(request):
    """Devuelve {'bytes','sheets','current'} o None."""
    return cache.get(f"{XLSX_PREFIX}{_sid(request)}")


def clear_excel(request) -> None:
    cache.delete(f"{XLSX_PREFIX}{_sid(request)}")


def _core_models():
    try:
        return list(apps.get_app_config("core").get_models())
    except LookupError:
        return []


def list_models() -> list[dict]:
    """Modelos analizables de la app core: [{'value','label','count'}]."""
    out = []
    for model in _core_models():
        if model.__name__ in _HIDE_MODELS:
            continue
        try:
            count = model.objects.count()
        except Exception:
            count = 0
        out.append({
            "value": model.__name__,
            "label": str(model._meta.verbose_name_plural).title(),
            "count": count,
        })
    return sorted(out, key=lambda m: m["label"])


def load_model_df(model_name: str, limit: int = 5000) -> pd.DataFrame:
    """Carga un modelo de core a DataFrame con .values() (FKs como <campo>_id)."""
    target = next((m for m in _core_models() if m.__name__ == model_name), None)
    if target is None:
        raise ValueError(f"Modelo desconocido: {model_name}")
    rows = list(target.objects.all().values()[: int(limit)])
    return pd.DataFrame(rows)


# ── Analytics por empresa (modo integrado, vía ORM) ─────────────────────────
# El objetivo del sistema: los gráficos se acotan siempre a UNA empresa — la
# que tiene sesión iniciada en producción (Company.owner == request.user), o
# la que elija un admin/superuser durante pruebas.
_SALES_RENAME = {
    "product__name": "producto", "product__sku": "sku",
    "product__category__name": "categoria",
    "order__order_number": "orden", "order__status": "estado_orden",
    "order__order_type": "tipo_orden", "order__created_at": "fecha",
    "order__total": "total_orden",
}


def list_companies() -> list[dict]:
    """[{'id','name'}] ordenadas por nombre, o [] si el modelo no existe."""
    try:
        Company = apps.get_model("core", "Company")
    except LookupError:
        return []
    return list(Company.objects.order_by("name").values("id", "name"))


def company_for_user(user) -> dict | None:
    """{'id','name'} de la empresa que este usuario posee (Company.owner), o None."""
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        Company = apps.get_model("core", "Company")
    except LookupError:
        return None
    return Company.objects.filter(owner_id=user.id).values("id", "name").first()


def load_company_sales_df(company_id: int, limit: int = 20000) -> pd.DataFrame:
    """Líneas de venta (OrderItem) de los productos de una empresa, con datos
    de producto y orden ya unidos — no IDs sueltos."""
    OrderItem = apps.get_model("core", "OrderItem")
    rows = list(
        OrderItem.objects.filter(product__company_id=company_id)
        .values(
            "qty", "unit_price_snapshot", "line_total",
            "product__name", "product__sku", "product__category__name",
            "order__order_number", "order__status", "order__order_type",
            "order__created_at", "order__total",
        )[: int(limit)]
    )
    df = pd.DataFrame(rows)
    return df.rename(columns=_SALES_RENAME) if not df.empty else df


# ── Analytics por empresa (modo standalone, vía SQL directo) ────────────────
def sql_has_tradeflow_schema(tables: list[dict]) -> bool:
    """True si la BD conectada tiene el esquema de Tradeflow (para mostrar el
    selector de empresa solo cuando tiene sentido)."""
    names = {t["name"] for t in tables}
    return {"core_company", "core_product", "core_orderitem", "core_order"}.issubset(names)


def sql_list_companies(conn_str: str, schema: str = "public") -> list[dict]:
    from .engine import db_connector
    df = db_connector.run_query(conn_str, f'SELECT id, name FROM "{schema}"."core_company" ORDER BY name')
    return df.to_dict("records") if not df.empty else []


def sql_load_company_sales(conn_str: str, company_id: int, schema: str = "public",
                           limit: int = 20000) -> pd.DataFrame:
    from .engine import db_connector
    cid = int(company_id)  # sanitiza: solo un entero puede llegar al SQL
    sql = f"""
        SELECT oi.qty, oi.unit_price_snapshot, oi.line_total,
               p.name AS producto, p.sku AS sku, cat.name AS categoria,
               o.order_number AS orden, o.status AS estado_orden,
               o.order_type AS tipo_orden, o.created_at AS fecha, o.total AS total_orden
        FROM "{schema}"."core_orderitem" oi
        JOIN "{schema}"."core_product" p ON oi.product_id = p.id
        JOIN "{schema}"."core_order" o ON oi.order_id = o.id
        LEFT JOIN "{schema}"."core_category" cat ON p.category_id = cat.id
        WHERE p.company_id = {cid}
        LIMIT {int(limit)}
    """
    return db_connector.run_query(conn_str, sql)
