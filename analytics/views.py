"""Django views for TradeFlow Analytics IA (DataFlow on Django).

Seller Mi Tienda dashboard auto-loads owner company sales; staff admin
dashboard supports multi-source load, hybrid chat, forecasts, and export
for Colon Free Zone marketplace analytics.
"""
from __future__ import annotations
import io
import json
import logging
import os
from functools import lru_cache, wraps

import pandas as pd

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.decorators import seller_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
import plotly.io as pio

from .engine import (
    data_loader,
    table_generator as tg,
    chart_generator as cg,
    ai_analyzer,
    exporter,
    db_connector,
    forecasting,
    labels as L,
    table_present as TP,
)
from . import data_source as ds

MAX_CHART_ROWS = 50_000
logger = logging.getLogger("analytics")

# Standalone mode (ANALYTICS_STANDALONE): no login / TradeFlow DB required.
STANDALONE = getattr(settings, "ANALYTICS_STANDALONE", False)
BASE_TEMPLATE = "analytics/standalone_base.html" if STANDALONE else "core/base.html"


def config(key: str, default: str = "") -> str:
    """Read an env var, loading BASE_DIR/.env once if needed (no decouple)."""
    if key not in os.environ:
        try:
            from dotenv import load_dotenv
            base = getattr(settings, "BASE_DIR", None)
            load_dotenv(os.path.join(str(base), ".env") if base else None)
        except Exception:
            pass
    return os.environ.get(key, default)


def _login(view):
    """Apply login_required unless ANALYTICS_STANDALONE is enabled."""
    return view if STANDALONE else login_required(view)


def _staff_required(view):
    """Restrict multi-source tools to staff/superuser (or standalone).

    Blocks ordinary sellers from admin dashboard, ORM model load, and
    db_connect under the seller portal URL.
    """
    if STANDALONE:
        return view

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """Allow staff through; redirect sellers to embedded analytics."""
        if request.user.is_staff or request.user.is_superuser:
            return view(request, *args, **kwargs)
        from django.contrib import messages as dj_messages
        dj_messages.error(request, "Esta herramienta solo está disponible para administradores.")
        return redirect("analytics:seller_dashboard")
    return wrapper


def _is_staff_user(user) -> bool:
    """True when the user is staff or superuser."""
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _api_key() -> str:
    """NVIDIA/LLM API key for cloud NIM; empty for local self-hosted."""
    # Self-hosted NIM needs no key (engine uses "not-needed"); this is for
    # NVIDIA cloud API (NVIDIA_API_KEY).
    return config("NVIDIA_API_KEY", default="") or config("LLM_API_KEY", default="")


@lru_cache(maxsize=1)
def _plotlyjs() -> str:
    """Cached Plotly.js bundle for offline serving."""
    from plotly.offline import get_plotlyjs
    return get_plotlyjs()


def plotlyjs(request):
    """Serve bundled Plotly.js so dashboards work without a CDN."""
    resp = HttpResponse(_plotlyjs(), content_type="application/javascript")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


def _is_dark(request) -> bool:
    """Resolve dark theme from ?theme= and persist it in the session."""
    choice = request.GET.get("theme")
    if choice in ("dark", "light"):
        request.session["analytics_theme"] = choice
    return request.session.get("analytics_theme") == "dark"


# ── Dashboard ────────────────────────────────────────────────────────────────
def _auto_connect_db(request) -> str | None:
    """Standalone: auto-connect ANALYTICS_DB_URL when no DB is cached yet.

    Returns an error string for the UI if connect fails; None on skip/success.
    """
    if not STANDALONE or ds.get_db(request):
        return None
    uri = config("ANALYTICS_DB_URL", default="")
    if not uri:
        return None
    try:
        uri = db_connector.normalize_conn_str(uri)
        db_connector.test_connection(uri)
        tables = db_connector.list_tables(uri, "public")
        try:
            fks = db_connector.list_foreign_keys(uri, "public")
        except Exception:
            fks = []
        ds.store_db(request, uri, tables, "public", fks)
        return None
    except Exception as e:
        logger.exception("Auto-conexión a ANALYTICS_DB_URL falló")
        return f"{type(e).__name__}: {e}"


@_staff_required
def dashboard(request):
    """Staff multi-source Analytics dashboard (KPIs, charts, chat, DB)."""
    db_auto_error = _auto_connect_db(request)
    df, meta = ds.get_df(request)
    dark = _is_dark(request)
    db = ds.get_db(request)
    xls = ds.get_excel(request)
    ctx = {
        "nav_activo": "analytics",
        "base_template": BASE_TEMPLATE,
        "models": ds.list_models(),
        "has_data": df is not None,
        "meta": meta,
        "dark": dark,
        "db_available": db_connector.available(),
        "db_connected": db is not None,
        "db_auto_error": db_auto_error,
        "db_tables": db["tables"] if db else [],
        "db_schema": db.get("schema", "public") if db else "public",
        "db_fks": db.get("fks", []) if db else [],
        "excel_sheets": xls["sheets"] if xls else [],
        "excel_current": xls["current"] if xls else "",
    }
    ctx.update(_company_context(request, db))
    if df is not None:
        if meta.get("company"):
            ctx.update(_company_dashboard_context(df, dark))
            ctx["company_view"] = True
        else:
            ctx.update(_dashboard_context(df, dark))
    return render(request, "analytics/dashboard.html", ctx)


def _load_seller_company_df(request):
    """Load joined OrderItem sales for the signed-in seller's company.

    Returns (df, company, load_meta). Never trusts a company id from the
    request — only Company.owner — to prevent cross-tenant leaks.
    """
    company = ds.company_for_user(request.user)
    if not company:
        return None, None, {}
    try:
        df, load_meta = ds.load_company_sales_bundle(company["id"])
        df = data_loader.clean(df)
    except Exception:
        logger.exception("seller analytics: fallo al cargar ventas de la empresa")
        return None, company, {}
    return df, company, load_meta


@seller_required
def seller_dashboard(request):
    """Embedded Mi Tienda Analytics IA for the signed-in CFZ seller.

    Reloads owner company sales from the ORM each visit (safe under multi-
    worker LocMem). No arbitrary file/DB/SQL sources for sellers.
    """
    dark = _is_dark(request)
    ctx = {
        "base_template": "core/seller_layout.html",
        "seller_embedded": True,
        "company_view": True,
        "company_mode": None,          # sin selector de empresa
        "dark": dark,
        "nav_activo": "analytics",
        "has_data": False,
    }
    df, company, load_meta = _load_seller_company_df(request)
    ctx["company_name"] = company["name"] if company else ""
    if not company:
        ctx["no_company"] = True
        return render(request, "analytics/seller_dashboard.html", ctx)
    if df is None or df.empty:
        ctx["no_sales"] = True
        return render(request, "analytics/seller_dashboard.html", ctx)

    ds.store_df(request, df, {"company": True, "origen": company["name"], **load_meta})
    ctx["has_data"] = True
    ctx["meta"] = {"company": True, "origen": company["name"], **load_meta}
    ctx["data_truncated"] = bool(load_meta.get("truncated"))
    ctx["data_total_rows"] = load_meta.get("total_rows")
    ctx["data_limit"] = load_meta.get("limit")
    ctx["ui_lang"] = "en"
    dash = _company_dashboard_context(df, dark, lang="en")
    ctx.update(dash)
    ctx["forecast_available"] = bool(dash.get("proj_tables") or dash.get("forecast_charts"))
    return render(request, "analytics/seller_dashboard.html", ctx)


def _company_context(request, db: dict | None) -> dict:
    """Build company picker context for staff/standalone company-scoped loads.

    Sellers get their owned company; staff may pick any; standalone shows
    companies only when the connected DB has TradeFlow schema.
    """
    empty = {"company_mode": None, "companies": [], "my_company": None, "is_company_admin": False}
    if STANDALONE:
        if db and ds.sql_has_tradeflow_schema(db["tables"]):
            try:
                companies = ds.sql_list_companies(db["conn"], db.get("schema", "public"))
            except Exception:
                companies = []
            return {"company_mode": "sql", "companies": companies,
                    "my_company": None, "is_company_admin": True}
        return empty

    user = request.user
    is_admin = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    my_company = ds.company_for_user(user)
    if not is_admin and not my_company:
        return empty
    companies = ds.list_companies() if is_admin else ([my_company] if my_company else [])
    return {"company_mode": "orm", "companies": companies,
            "my_company": my_company, "is_company_admin": is_admin}


_PER = {"D": "día", "W": "semana", "M": "mes", "Q": "trimestre", "Y": "año"}
_PER_PL = {"D": "días", "W": "semanas", "M": "meses", "Q": "trimestres", "Y": "años"}


def _auto_projections(d, dark: bool = False, metric: str | None = None,
                      item: str | None = None, money: bool = True, lang: str = "es"):
    """Build auto forecast chart plus rising/falling product tables."""
    charts, tables = [], []
    date_col = forecasting.find_date_column(d)
    num_cols = list(d.select_dtypes(include="number").columns)
    if not date_col or not num_cols:
        return charts, tables
    metric = metric if metric in d.columns else (
        "line_total" if "line_total" in d.columns else num_cols[0])
    ml = L.pretty(metric, lang=lang)
    freq = forecasting.auto_freq(d, date_col)
    periods = forecasting.default_horizon(freq)
    if lang == "en":
        per_map = {"D": "day", "W": "week", "M": "month", "Q": "quarter", "Y": "year"}
        per_pl_map = {"D": "days", "W": "weeks", "M": "months", "Q": "quarters", "Y": "years"}
        per, per_pl = per_map.get(freq, "period"), per_pl_map.get(freq, "periods")
    else:
        per, per_pl = _PER.get(freq, "período"), _PER_PL.get(freq, "períodos")
    fmt = (lambda v: f"${v:,.0f}") if money else (lambda v: f"{v:,.0f}")

    ts = forecasting.build_series(d, date_col, metric, freq=freq, agg="sum")
    r = forecasting.linear_forecast(ts, periods) if ts is not None else None
    if r:
        try:
            ftitle = f"Forecast · {ml}" if lang == "en" else f"Proyección de {ml}"
            fig = cg.forecast_chart(r, title=ftitle, y_title=ml)
            if fig is not None:
                charts.append({"title": ftitle,
                               "fig": pio.to_json(cg.apply_theme(fig, dark))})
        except Exception:
            pass
        growth = f"{r['proj_growth_pct']:+.1f}%" if r.get("proj_growth_pct") is not None else ("n/a" if lang == "en" else "s/d")
        cagr = f"{r['cagr']:+.1f}%" if r.get("cagr") is not None else ("n/a" if lang == "en" else "s/d")
        if lang == "en":
            conf = "high" if r["r2"] >= 0.7 else "medium" if r["r2"] >= 0.4 else "low"
            summary_rows = [
                {"label": f"{ml} in the last {per}", "value": fmt(r["last"]), "tone": "neutral"},
                {"label": f"Forecast for next {per}", "value": fmt(r["proj_last"]), "tone": "neutral"},
                {"label": "Estimated growth (next period)", "value": growth,
                 "tone": "up" if str(growth).startswith("+") else "down" if str(growth).startswith("-") else "flat"},
                {"label": "Historical CAGR", "value": cagr,
                 "tone": "up" if str(cagr).startswith("+") else "down" if str(cagr).startswith("-") else "flat"},
                {"label": f"Projected total ({periods} {per_pl})", "value": fmt(r["proj_total"]), "tone": "neutral"},
                {"label": "Model confidence", "value": f"{conf} (R²={r['r2']:.2f})", "tone": "muted"},
            ]
            summary = pd.DataFrame({
                "Metric": [row["label"] for row in summary_rows],
                "Value": [row["value"] for row in summary_rows],
            })
            tables.append({
                "title": f"Forecast · {ml} — next {periods} {per_pl}",
                "html": TP.dataframe_html(summary),
                "rows": summary_rows,
                "note": "Linear trend on your history; the chart shows the likely range.",
                "kind": "summary",
            })
        else:
            conf = "alta" if r["r2"] >= 0.7 else "media" if r["r2"] >= 0.4 else "baja"
            summary_rows = [
                {"label": f"{ml} en el último {per}", "value": fmt(r["last"]), "tone": "neutral"},
                {"label": f"Proyección para el próximo {per}", "value": fmt(r["proj_last"]), "tone": "neutral"},
                {"label": "Crecimiento estimado (próximo período)", "value": growth,
                 "tone": "up" if str(growth).startswith("+") else "down" if str(growth).startswith("-") else "flat"},
                {"label": "Crecimiento compuesto histórico (CAGR)", "value": cagr,
                 "tone": "up" if str(cagr).startswith("+") else "down" if str(cagr).startswith("-") else "flat"},
                {"label": f"Total proyectado ({periods} {per_pl})", "value": fmt(r["proj_total"]), "tone": "neutral"},
                {"label": "Confianza del modelo", "value": f"{conf} (R²={r['r2']:.2f})", "tone": "muted"},
            ]
            summary = pd.DataFrame({
                "Indicador": [row["label"] for row in summary_rows],
                "Valor": [row["value"] for row in summary_rows],
            })
            tables.append({
                "title": f"Proyección de {ml} — próximos {periods} {per_pl}",
                "html": TP.dataframe_html(summary),
                "rows": summary_rows,
                "note": "Tendencia lineal sobre el histórico; el rango probable se ve en la gráfica.",
                "kind": "summary",
            })

    item = item if item in d.columns else ("producto" if "producto" in d.columns else None)
    if item:
        try:
            tr = forecasting.item_trends(d, item, date_col, metric, freq=freq)
        except Exception:
            tr = None
        if tr is not None and not tr.empty:
            def _tbl(t):
                """Format a rising/falling product table as HTML."""
                x = t[[item, "total", "cambio_pct"]].copy()
                x["total"] = x["total"].map(fmt)            # formatear ANTES de renombrar
                x["cambio_pct"] = x["cambio_pct"].map(lambda v: f"{v:+.0f}%")
                change_h = "Change %" if lang == "en" else "Cambio %"
                x.columns = [L.pretty(item, lang=lang), f"{ml} (total)", change_h]
                return TP.dataframe_html(x, delta_cols=[change_h])
            rising = tr[tr["cambio_pct"] > 8].sort_values("cambio_pct", ascending=False).head(5)
            falling = tr[tr["cambio_pct"] < -8].sort_values("cambio_pct").head(5)
            if not rising.empty:
                tables.append({
                    "title": "Rising products (forecast)" if lang == "en" else "Productos al alza (proyección)",
                    "html": _tbl(rising),
                    "rows": None,
                    "note": ("Fastest growth from first to second half of history."
                             if lang == "en" else
                             "Mayor crecimiento entre la 1ª y la 2ª mitad del histórico."),
                    "kind": "up",
                })
            if not falling.empty:
                tables.append({
                    "title": "Falling products (review)" if lang == "en" else "Productos a la baja (a revisar)",
                    "html": _tbl(falling),
                    "rows": None,
                    "kind": "down",
                    "note": ("Largest sales drop — worth reviewing."
                             if lang == "en" else
                             "Mayor caída de ventas — candidatos a revisar."),
                })
    return charts, tables


def _dashboard_context(df, dark: bool = False) -> dict:
    """Generic multi-source dashboard KPIs, auto-charts, and forecasts."""
    num_cols = tg.detect_numeric_columns(df)
    cat_cols = tg.detect_categorical_columns(df)
    nulls = int(df.isnull().sum().sum())
    completos = 100 - (nulls / max(df.size, 1) * 100)
    kpis = [
        ("Filas", f"{df.shape[0]:,}"),
        ("Columnas", str(df.shape[1])),
        ("Numéricas", str(len(num_cols))),
        ("Categóricas", str(len(cat_cols))),
        ("Datos completos", f"{completos:.1f}%"),
    ]

    charts = []
    try:
        sample = df.sample(MAX_CHART_ROWS, random_state=42) if len(df) > MAX_CHART_ROWS else df
        generated = cg.auto_charts(sample)
    except Exception:
        generated = []
    # Cada gráfica se serializa por separado: si una falla (p. ej. datos no
    # serializables a JSON), no tumba a las demás.
    for title, fig in generated:
        if fig is None:
            continue
        try:
            charts.append({"title": title, "fig": pio.to_json(cg.apply_theme(fig, dark))})
        except Exception:
            continue

    proj_charts, proj_tables = _auto_projections(df, dark, money=False)

    preview = df.head(100)
    return {
        "kpis": kpis,
        "charts": charts,
        "forecast_charts": proj_charts,
        "proj_tables": proj_tables,
        "preview_html": TP.dataframe_html(L.pretty_columns(preview)),
        "n_preview": min(100, len(df)),
        "n_total": len(df),
    }


def _company_dashboard_context(df, dark: bool = False, lang: str = "es") -> dict:
    """CFZ company sales KPIs, charts, and forecasts (lang=en for sellers)."""
    d = df.copy()
    if "fecha" in d.columns:
        try:
            f = pd.to_datetime(d["fecha"], errors="coerce")
            if getattr(f.dt, "tz", None) is not None:
                f = f.dt.tz_localize(None)
            d["dia"] = f.dt.floor("D")
        except Exception:
            pass

    ingresos = float(d["line_total"].sum()) if "line_total" in d.columns else 0.0
    ordenes = int(d["orden"].nunique()) if "orden" in d.columns else 0
    unidades = int(d["qty"].sum()) if "qty" in d.columns else 0
    ticket = (ingresos / ordenes) if ordenes else 0.0
    productos = int(d["producto"].nunique()) if "producto" in d.columns else 0
    if lang == "en":
        kpis = [
            ("Revenue", f"${ingresos:,.0f}"),
            ("Orders", f"{ordenes:,}"),
            ("Units sold", f"{unidades:,}"),
            ("Avg. order value", f"${ticket:,.0f}"),
            ("Products sold", f"{productos:,}"),
        ]
    else:
        kpis = [
            ("Ingresos", f"${ingresos:,.0f}"),
            ("Órdenes", f"{ordenes:,}"),
            ("Unidades vendidas", f"{unidades:,}"),
            ("Ticket promedio", f"${ticket:,.0f}"),
            ("Productos vendidos", f"{productos:,}"),
        ]

    charts: list[dict] = []

    def add(title, fn):
        """Append a themed chart JSON; skip failures without aborting."""
        try:
            fig = fn()
            if fig is not None:
                charts.append({"title": title, "fig": pio.to_json(cg.apply_theme(fig, dark))})
        except Exception:
            pass

    cols = set(d.columns)
    if lang == "en":
        if {"dia", "line_total"} <= cols:
            add("Revenue over time", lambda: cg.line_chart(d, "dia", "line_total"))
        if {"producto", "line_total"} <= cols:
            add("Top products by revenue", lambda: cg.grouped_bar(d, "producto", "line_total"))
        if {"categoria", "line_total"} <= cols:
            add("Revenue by category", lambda: cg.grouped_bar(d, "categoria", "line_total"))
        if {"estado_orden", "line_total"} <= cols:
            add("Sales by order status", lambda: cg.funnel(d, "estado_orden", "line_total"))
        if "tipo_orden" in cols:
            add("Mix by order type", lambda: cg.pie_chart(d, "tipo_orden"))
        if {"categoria", "producto", "line_total"} <= cols:
            add("Category → product composition", lambda: cg.treemap(d, ["categoria", "producto"], "line_total"))
        if {"producto", "qty"} <= cols:
            add("Units sold by product", lambda: cg.grouped_bar(d, "producto", "qty"))
    else:
        if {"dia", "line_total"} <= cols:
            add("Ingresos en el tiempo", lambda: cg.line_chart(d, "dia", "line_total"))
        if {"producto", "line_total"} <= cols:
            add("Top productos por ingresos", lambda: cg.grouped_bar(d, "producto", "line_total"))
        if {"categoria", "line_total"} <= cols:
            add("Ingresos por categoría", lambda: cg.grouped_bar(d, "categoria", "line_total"))
        if {"estado_orden", "line_total"} <= cols:
            add("Ventas por estado de la orden", lambda: cg.funnel(d, "estado_orden", "line_total"))
        if "tipo_orden" in cols:
            add("Proporción por tipo de orden", lambda: cg.pie_chart(d, "tipo_orden"))
        if {"categoria", "producto", "line_total"} <= cols:
            add("Composición categoría → producto", lambda: cg.treemap(d, ["categoria", "producto"], "line_total"))
        if {"producto", "qty"} <= cols:
            add("Unidades vendidas por producto", lambda: cg.grouped_bar(d, "producto", "qty"))

    proj_charts, proj_tables = _auto_projections(
        d, dark, metric="line_total", item="producto", lang=lang,
    )

    preview = df.head(100)
    return {
        "kpis": kpis,
        "charts": charts,
        "forecast_charts": proj_charts,
        "proj_tables": proj_tables,
        "preview_html": TP.dataframe_html(L.pretty_columns(preview, lang=lang)),
        "n_preview": min(100, len(df)),
        "n_total": len(df),
        "ui_lang": lang,
    }


# ── Carga de datos ───────────────────────────────────────────────────────────
@_staff_required
@require_POST
def load(request):
    """Load file/paste/ORM/DB data into the session working DataFrame."""
    source = request.POST.get("source")
    ds.clear_excel(request)   # cualquier carga nueva resetea el selector de hoja
    try:
        if source == "file":
            f = request.FILES.get("file")
            if not f:
                raise ValueError("No se seleccionó ningún archivo.")
            ext = f.name.rsplit(".", 1)[-1].lower()
            if ext == "csv":
                df = data_loader.load_csv(f)
                meta = {"origen": f.name}
            elif ext in ("xlsx", "xls"):
                data = f.read()
                sheets = data_loader.excel_sheet_names(io.BytesIO(data))
                if not sheets:
                    raise ValueError("El Excel no tiene hojas con datos.")
                chosen = data_loader.best_sheet_name(io.BytesIO(data))
                df = data_loader.load_excel_sheet(io.BytesIO(data), chosen)
                if len(sheets) > 1:
                    ds.store_excel(request, data, sheets, chosen)  # permite cambiar de hoja
                meta = {"origen": f"{f.name} · hoja «{chosen}»"
                        if len(sheets) > 1 else f.name}
            elif ext == "json":
                df = data_loader.load_json(f)
                meta = {"origen": f.name}
            else:
                raise ValueError("Formato no soportado (usa CSV, Excel o JSON).")

        elif source == "paste":
            text = request.POST.get("text", "")
            if not text.strip():
                raise ValueError("No se pegó ningún dato.")
            df = data_loader.load_text(text)
            meta = {"origen": "Texto pegado"}

        elif source == "model":
            name = request.POST.get("model")
            limit = int(request.POST.get("limit") or 5000)
            df = ds.load_model_df(name, limit)
            meta = {"origen": f"Tradeflow · {name}"}

        elif source == "db":
            db = ds.get_db(request)
            if not db:
                raise ValueError("No hay conexión a base de datos. Conéctate primero.")
            table = request.POST.get("table")
            limit = int(request.POST.get("limit") or 5000)
            schema = db.get("schema", "public")
            if not table:
                raise ValueError("Selecciona una tabla.")
            if request.POST.get("joined"):
                df = db_connector.read_table_joined(db["conn"], table, schema, limit)
                meta = {"origen": f"BD · {table} (+relaciones)"}
            else:
                df = db_connector.read_table(db["conn"], table, schema, limit)
                meta = {"origen": f"BD · {table}"}

        elif source == "db_sql":
            db = ds.get_db(request)
            if not db:
                raise ValueError("No hay conexión a base de datos. Conéctate primero.")
            sql = request.POST.get("sql", "")
            df = db_connector.run_query(db["conn"], sql)
            meta = {"origen": "BD · SQL"}

        else:
            raise ValueError("Fuente de datos inválida.")

        df = data_loader.clean(df)
        if df is None or df.empty:
            raise ValueError("El conjunto de datos quedó vacío.")
        ds.store_df(request, df, meta)
        messages.success(
            request, f"✓ Cargado: {df.shape[0]:,} filas × {df.shape[1]} columnas"
        )
    except Exception as e:
        logger.exception("Error al cargar datos (source=%s)", source)
        messages.error(request, f"Error al cargar: {type(e).__name__}: {e}")
    return redirect("analytics:dashboard")


@_staff_required
@require_POST
def clear(request):
    """Discard the session dataset and cached Excel workbook."""
    ds.clear_df(request)
    ds.clear_excel(request)
    messages.info(request, "Datos descartados.")
    return redirect("analytics:dashboard")


@_staff_required
@require_POST
def load_sheet(request):
    """Switch the working sheet from the cached multi-sheet Excel upload."""
    info = ds.get_excel(request)
    sheet = request.POST.get("sheet")
    try:
        if not info:
            raise ValueError("No hay un Excel cargado.")
        if sheet not in info["sheets"]:
            raise ValueError("Hoja no encontrada.")
        df = data_loader.clean(data_loader.load_excel_sheet(io.BytesIO(info["bytes"]), sheet))
        if df is None or df.empty:
            raise ValueError(f"La hoja «{sheet}» no tiene datos tabulares.")
        ds.store_df(request, df, {"origen": f"Excel · hoja «{sheet}»"})
        ds.store_excel(request, info["bytes"], info["sheets"], sheet)
        messages.success(request, f"✓ Hoja «{sheet}»: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    except Exception as e:
        logger.exception("Error al cargar hoja")
        messages.error(request, f"Error al cargar la hoja: {type(e).__name__}: {e}")
    return redirect("analytics:dashboard")


# ── Analytics acotado a una empresa ─────────────────────────────────────────
@_staff_required
@require_POST
def load_company(request):
    """Load one CFZ company's sales into the staff analytics session."""
    try:
        company_id = int(request.POST.get("company_id"))
    except (TypeError, ValueError):
        messages.error(request, "Selecciona una empresa válida.")
        return redirect("analytics:dashboard")

    try:
        if STANDALONE:
            db = ds.get_db(request)
            if not db or not ds.sql_has_tradeflow_schema(db["tables"]):
                raise ValueError("Conéctate a una base con el esquema de Tradeflow primero.")
            schema = db.get("schema", "public")
            companies = ds.sql_list_companies(db["conn"], schema)
            company = next((c for c in companies if c["id"] == company_id), None)
            df = ds.sql_load_company_sales(db["conn"], company_id, schema)
        else:
            is_admin = bool(getattr(request.user, "is_staff", False)
                            or getattr(request.user, "is_superuser", False))
            my_company = ds.company_for_user(request.user)
            if not is_admin and (not my_company or my_company["id"] != company_id):
                raise PermissionError("No tienes acceso a los datos de esa empresa.")
            companies = ds.list_companies()
            company = next((c for c in companies if c["id"] == company_id), None)
            df = ds.load_company_sales_df(company_id)

        name = company["name"] if company else f"Empresa #{company_id}"
        df = data_loader.clean(df)
        if df is None or df.empty:
            raise ValueError(f"«{name}» no tiene ventas registradas todavía.")
        ds.store_df(request, df, {"origen": f"Empresa · {name}", "company": True})
        messages.success(request, f"✓ {name}: {df.shape[0]:,} líneas de venta cargadas")
    except Exception as e:
        logger.exception("Error al cargar empresa")
        messages.error(request, f"Error: {type(e).__name__}: {e}")
    return redirect("analytics:dashboard")


# ── Conexión a base de datos (Supabase/PostgreSQL) ──────────────────────────
@_staff_required
@require_POST
def db_connect(request):
    """Test and cache a read-only Postgres/MySQL connection for staff loads."""
    conn_str = db_connector.normalize_conn_str(request.POST.get("conn", ""))
    schema = request.POST.get("schema") or "public"
    try:
        db_connector.test_connection(conn_str)
        tables = db_connector.list_tables(conn_str, schema)
        try:
            fks = db_connector.list_foreign_keys(conn_str, schema)
        except Exception:
            fks = []
        ds.store_db(request, conn_str, tables, schema, fks)
        if tables:
            messages.success(
                request,
                f"✓ Conectado · {len(tables)} tablas · {len(fks)} relaciones en «{schema}»",
            )
        else:
            messages.warning(request, f"Conectado, pero no hay tablas en «{schema}».")
    except Exception as e:
        ds.clear_db(request)
        messages.error(request, f"No se pudo conectar: {e}")
    return redirect("analytics:dashboard")


@_staff_required
@require_POST
def db_disconnect(request):
    """Clear the cached database connection from the session."""
    ds.clear_db(request)
    messages.info(request, "Desconectado de la base de datos.")
    return redirect("analytics:dashboard")


# ── Chat híbrido ─────────────────────────────────────────────────────────────
@_login
@require_POST
def chat(request):
    """Hybrid AJAX chat: charts, tables, forecasts, and LLM Q&A.

    Non-staff sellers always bind to their company sales (never a stale
    multi-source cache from /admin/ tooling).
    """
    seller_ui = not STANDALONE and not _is_staff_user(request.user)
    ui_lang = "en" if seller_ui else "es"
    if seller_ui:
        df, company, load_meta = _load_seller_company_df(request)
        if df is not None and not df.empty and company:
            ds.store_df(request, df, {"company": True, "origen": company["name"], **load_meta})
        else:
            df = None
    else:
        df, _meta = ds.get_df(request)
        if df is None and not STANDALONE:
            # Resiliencia multi-worker: si la caché de sesión no tiene el df (otro
            # worker Gunicorn con LocMem sin Redis), recargar las ventas de la empresa
            # del vendedor desde el ORM en vez de pedirle que "cargue datos".
            df, company, load_meta = _load_seller_company_df(request)
            if df is not None and not df.empty and company:
                ds.store_df(request, df, {"company": True, "origen": company["name"], **load_meta})
    if df is None:
        msg = ("Load sales data first." if ui_lang == "en"
               else "Primero carga datos para analizar.")
        return JsonResponse({"text": msg, "fig": None, "table": None})
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    message = (body.get("message") or "").strip()
    history = body.get("history") or []
    if not message:
        msg = ("Type a question or request." if ui_lang == "en"
               else "Escribe una pregunta o petición.")
        return JsonResponse({"text": msg, "fig": None, "table": None})

    try:
        text, fig, table = ai_analyzer.chat(
            df, history, message, api_key=_api_key(), lang=ui_lang,
        )
    except Exception as e:
        return JsonResponse({"text": f"⚠ Error: {e}", "fig": None, "table": None})

    if fig is not None:
        cg.apply_theme(fig, request.session.get("analytics_theme") == "dark")
    fig_json = pio.to_json(fig) if fig is not None else None
    table_html = None
    if table is not None and not table.empty:
        table_html = TP.dataframe_html(
            L.pretty_columns(table.head(200), lang=ui_lang),
        )
    return JsonResponse({"text": text, "fig": fig_json, "table": table_html})


# ── Exportación ──────────────────────────────────────────────────────────────
@_login
def export(request, fmt):
    """Download CSV or multi-sheet Excel of the active analytics dataset."""
    if not STANDALONE and not _is_staff_user(request.user):
        df, company, load_meta = _load_seller_company_df(request)
        if df is None or df.empty:
            messages.error(request, "No data to export.")
            return redirect("analytics:seller_dashboard")
        if company:
            ds.store_df(request, df, {"company": True, "origen": company["name"], **load_meta})
        redirect_name = "analytics:seller_dashboard"
    else:
        df, _meta = ds.get_df(request)
        redirect_name = "analytics:dashboard"
        if df is None:
            messages.error(request, "No hay datos para exportar.")
            return redirect(redirect_name)

    export_lang = "en" if (not STANDALONE and not _is_staff_user(request.user)) else "es"
    df = L.pretty_columns(df, lang=export_lang)

    if fmt == "csv":
        resp = HttpResponse(exporter.to_csv(df), content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="analytics.csv"'
        return resp

    sheets = {"Datos": tg.raw_table(df)}
    stats = tg.statistics_table(df)
    if stats is not None:
        sheets["Estadísticas"] = stats
    sheets["Calidad"] = tg.missing_values_table(df)
    corr = tg.correlation_table(df)
    if corr is not None:
        sheets["Correlación"] = corr
    resp = HttpResponse(
        exporter.to_excel(sheets),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = 'attachment; filename="analytics.xlsx"'
    return resp
