"""Session-scoped data sources for TradeFlow Analytics IA.

Caches loaded DataFrames between requests (Django cache, keyed by
session — Streamlit used session_state). Also loads CFZ seller sales
directly from core ORM models without file export.
"""
from __future__ import annotations
import pandas as pd
from django.apps import apps
from django.core.cache import cache

CACHE_PREFIX = "analytics:df:"
DB_PREFIX = "analytics:db:"
CACHE_TIMEOUT = 60 * 60  # 1 hour

# Technical models that add no seller-analytics value
_HIDE_MODELS = {"Session", "LogEntry", "AccessAttempt", "AccessLog",
                "AccessFailureLog", "ContentType", "Permission"}


def _sid(request) -> str:
    """Ensure a session key exists and return it as a cache id."""
    if not request.session.session_key:
        request.session.save()
    return str(request.session.session_key)


def store_df(request, df: pd.DataFrame, meta: dict | None = None) -> None:
    """Persist the working DataFrame and meta for this browser session."""
    cache.set(f"{CACHE_PREFIX}{_sid(request)}", {"df": df, "meta": meta or {}}, CACHE_TIMEOUT)


def get_df(request):
    """Return (DataFrame, meta) for the session, or (None, {})."""
    payload = cache.get(f"{CACHE_PREFIX}{_sid(request)}")
    if not payload:
        return None, {}
    return payload["df"], payload.get("meta", {})


def clear_df(request) -> None:
    """Drop the cached working DataFrame for this session."""
    cache.delete(f"{CACHE_PREFIX}{_sid(request)}")


# ── Database connection (Supabase/PostgreSQL) ────────────────────────────────
def store_db(request, conn_str: str, tables: list, schema: str = "public",
             fks: list | None = None) -> None:
    """Cache a read-only DB connection handle and schema inventory."""
    cache.set(
        f"{DB_PREFIX}{_sid(request)}",
        {"conn": conn_str, "tables": tables, "schema": schema, "fks": fks or []},
        CACHE_TIMEOUT,
    )


def get_db(request):
    """Return cached DB payload {conn, tables, schema, fks} or None."""
    return cache.get(f"{DB_PREFIX}{_sid(request)}")


def clear_db(request) -> None:
    """Forget the cached database connection for this session."""
    cache.delete(f"{DB_PREFIX}{_sid(request)}")


# ── Multi-sheet Excel: keep bytes so sheet switches skip re-upload ───────────
XLSX_PREFIX = "analytics:xlsx:"


def store_excel(request, data: bytes, sheets: list, current: str) -> None:
    """Cache uploaded workbook bytes and the active sheet name."""
    cache.set(f"{XLSX_PREFIX}{_sid(request)}",
              {"bytes": data, "sheets": sheets, "current": current}, CACHE_TIMEOUT)


def get_excel(request):
    """Return cached Excel payload {bytes, sheets, current} or None."""
    return cache.get(f"{XLSX_PREFIX}{_sid(request)}")


def clear_excel(request) -> None:
    """Drop cached Excel bytes for this session."""
    cache.delete(f"{XLSX_PREFIX}{_sid(request)}")


def _core_models():
    """List registered core app models, or [] if core is unavailable."""
    try:
        return list(apps.get_app_config("core").get_models())
    except LookupError:
        return []


def list_models() -> list[dict]:
    """Analyzable core models as [{value, label, count}]."""
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
    """Load a core model into a DataFrame via .values() (FKs as *_id)."""
    target = next((m for m in _core_models() if m.__name__ == model_name), None)
    if target is None:
        raise ValueError(f"Modelo desconocido: {model_name}")
    rows = list(target.objects.all().values()[: int(limit)])
    return pd.DataFrame(rows)


# ── Per-company analytics (integrated mode, via ORM) ─────────────────────────
# Charts always scope to ONE company — the signed-in owner's Company, or the
# company a staff/superuser picks while testing.
_SALES_RENAME = {
    "product__name": "producto", "product__sku": "sku",
    "product__category__name": "categoria",
    "order__order_number": "orden", "order__status": "estado_orden",
    "order__order_type": "tipo_orden", "order__created_at": "fecha",
    "order__total": "total_orden",
}


def list_companies() -> list[dict]:
    """Return [{id, name}] sorted by name, or [] if Company is missing."""
    try:
        Company = apps.get_model("core", "Company")
    except LookupError:
        return []
    return list(Company.objects.order_by("name").values("id", "name"))


def company_for_user(user) -> dict | None:
    """Return {id, name} for Company.owner == user, or None."""
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        Company = apps.get_model("core", "Company")
    except LookupError:
        return None
    return Company.objects.filter(owner_id=user.id).values("id", "name").first()


COMPANY_SALES_LIMIT = 20_000


def load_company_sales_df(company_id: int, limit: int = COMPANY_SALES_LIMIT) -> pd.DataFrame:
    """Load OrderItem lines for a CFZ seller company with product/order joins.

    Newest orders first so the row cap keeps recent marketplace activity.
    """
    OrderItem = apps.get_model("core", "OrderItem")
    rows = list(
        OrderItem.objects.filter(product__company_id=company_id)
        .order_by("-order__created_at", "-id")
        .values(
            "qty", "unit_price_snapshot", "line_total",
            "product__name", "product__sku", "product__category__name",
            "order__order_number", "order__status", "order__order_type",
            "order__created_at", "order__total",
        )[: int(limit)]
    )
    df = pd.DataFrame(rows)
    return df.rename(columns=_SALES_RENAME) if not df.empty else df


def company_sales_row_count(company_id: int) -> int:
    """Total OrderItem lines for the company (no load cap)."""
    OrderItem = apps.get_model("core", "OrderItem")
    return int(OrderItem.objects.filter(product__company_id=company_id).count())


def load_company_sales_bundle(company_id: int, limit: int = COMPANY_SALES_LIMIT) -> tuple[pd.DataFrame, dict]:
    """Return sales DataFrame plus truncation meta for seller UI banners."""
    limit = int(limit)
    total = company_sales_row_count(company_id)
    df = load_company_sales_df(company_id, limit=limit)
    return df, {
        "total_rows": total,
        "loaded_rows": 0 if df is None else int(len(df)),
        "limit": limit,
        "truncated": total > limit,
    }


# ── Per-company analytics (standalone mode, direct SQL) ─────────────────────
def sql_has_tradeflow_schema(tables: list[dict]) -> bool:
    """True when connected DB has TradeFlow core tables for company picker."""
    names = {t["name"] for t in tables}
    return {"core_company", "core_product", "core_orderitem", "core_order"}.issubset(names)


def sql_list_companies(conn_str: str, schema: str = "public") -> list[dict]:
    """List CFZ companies from a connected TradeFlow Postgres schema."""
    from .engine import db_connector
    df = db_connector.run_query(conn_str, f'SELECT id, name FROM "{schema}"."core_company" ORDER BY name')
    return df.to_dict("records") if not df.empty else []


def sql_load_company_sales(conn_str: str, company_id: int, schema: str = "public",
                           limit: int = 20000) -> pd.DataFrame:
    """Load company sales via SQL with the same column aliases as ORM load."""
    from .engine import db_connector
    cid = int(company_id)  # sanitize: only an int may reach the SQL
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
        ORDER BY o.created_at DESC, oi.id DESC
        LIMIT {int(limit)}
    """
    return db_connector.run_query(conn_str, sql)
