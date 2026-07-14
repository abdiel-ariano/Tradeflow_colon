"""
Motor de proyecciones a futuro para Analytics IA.

Sin dependencias nuevas (solo numpy + pandas). Entrega proyecciones honestas —
tendencia lineal por mínimos cuadrados + banda de incertidumbre a partir de los
residuos — más métricas de negocio (crecimiento %, CAGR) y detección de productos
en alza / en caída.

Todo es defensivo: devuelve None cuando no hay datos suficientes (mínimo ~3
períodos) en vez de lanzar excepción, para que el chat degrade con un aviso.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from . import labels as L

# Regla de resampleo por período (inicio de período para etiquetas limpias)
_FREQ_RULE = {"D": "D", "W": "W-MON", "M": "MS", "Q": "QS", "Y": "YS"}
_FREQ_LABEL = {"D": "día", "W": "semana", "M": "mes", "Q": "trimestre", "Y": "año"}
_FREQ_LABEL_PL = {"D": "días", "W": "semanas", "M": "meses", "Q": "trimestres", "Y": "años"}
_FREQ_LABEL_EN = {"D": "day", "W": "week", "M": "month", "Q": "quarter", "Y": "year"}
_FREQ_LABEL_PL_EN = {"D": "days", "W": "weeks", "M": "months", "Q": "quarters", "Y": "years"}
_DEFAULT_HORIZON = {"D": 14, "W": 8, "M": 6, "Q": 4, "Y": 3}
_DATE_HINTS = ("fecha", "date", "created", "creado", "timestamp", "periodo",
               "emitida", "emision", "dia", "day", "mes", "month")


# ── Detección y preparación de la serie ─────────────────────────────────────
def find_date_column(df: pd.DataFrame) -> str | None:
    """Primera columna usable como eje temporal: datetime real, o texto/columna
    parseable a fecha en >60% de sus valores."""
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        if any(h in str(c).lower() for h in _DATE_HINTS):
            s = _to_dt(df[c])
            if s.notna().mean() > 0.6:
                return c
    return None


def _to_dt(series: pd.Series) -> pd.Series:
    s = pd.to_datetime(series, errors="coerce", utc=True)
    try:
        s = s.dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return s


def auto_freq(df: pd.DataFrame, date_col: str) -> str:
    """Granularidad razonable según el rango de fechas de los datos."""
    s = _to_dt(df[date_col]).dropna()
    if s.empty:
        return "M"
    span = (s.max() - s.min()).days
    if span <= 31:
        return "D"
    if span <= 210:
        return "W"
    if span <= 1100:
        return "M"
    return "Q"


def default_horizon(freq: str) -> int:
    return _DEFAULT_HORIZON.get(freq, 6)


def parse_horizon(low_text: str) -> tuple[str | None, int | None]:
    """'próximos 6 meses' → ('M', 6). Devuelve (None, None) si no lo especifica.
    (low_text ya viene normalizado: sin acentos, minúsculas.)"""
    m = re.search(r"(\d+)\s*(dias?|semanas?|mes(?:es)?|trimestres?|anios?|anos?|years?)", low_text)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        freq = ("D" if unit.startswith("dia") else
                "W" if unit.startswith("semana") else
                "Q" if unit.startswith("trimestre") else
                "Y" if unit.startswith(("ani", "ano", "year")) else "M")
        return freq, max(1, min(n, 60))
    # Horizontes con nombre, sin número ("el próximo trimestre", "este año"):
    # se proyectan en meses para que la línea tenga varios puntos.
    if re.search(r"\btrimestre\b", low_text):
        return "M", 3
    if re.search(r"\bsemestre\b", low_text):
        return "M", 6
    if re.search(r"\b(anual|ano|anio|year)\b", low_text):
        return "M", 12
    if re.search(r"\bsemanas?\b", low_text):
        return "W", 8
    return None, None


def build_series(df: pd.DataFrame, date_col: str, value_col: str | None,
                 freq: str = "M", agg: str = "sum") -> pd.Series | None:
    """Serie temporal agregada por período. value_col=None → conteo de filas."""
    if date_col not in df.columns:
        return None
    cols = [date_col] + ([value_col] if value_col and value_col in df.columns else [])
    work = df[cols].copy()
    work[date_col] = _to_dt(work[date_col])
    work = work.dropna(subset=[date_col])
    if work.empty:
        return None
    rule = _FREQ_RULE.get(freq, "MS")
    idx = work.set_index(date_col).sort_index()
    if value_col and value_col in df.columns:
        fn = agg if agg in ("sum", "mean", "max", "min") else "sum"
        ts = getattr(idx[value_col].resample(rule), fn)()
    else:
        ts = idx.resample(rule).size()
    ts = ts.fillna(0.0)
    return ts if len(ts) >= 2 else None


# ── Proyección ──────────────────────────────────────────────────────────────
def linear_forecast(ts: pd.Series, periods: int = 6) -> dict | None:
    """Tendencia lineal (mínimos cuadrados) + banda de predicción ~95%.
    Devuelve history/forecast/low/high (Series) y métricas: slope, r2,
    growth_pct (histórico total), cagr (por período), proj_growth_pct."""
    y = np.asarray(ts.values, dtype=float)
    n = len(y)
    if n < 3:
        return None
    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fit = slope * x + intercept
    resid = y - fit
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    fx = np.arange(n, n + periods, dtype=float)
    fyhat = slope * fx + intercept
    # Intervalo de predicción aproximado (t≈2 → ~95%)
    dof = max(n - 2, 1)
    s_err = np.sqrt(ss_res / dof)
    mx = x.mean()
    sxx = float(np.sum((x - mx) ** 2)) or 1.0
    se_pred = s_err * np.sqrt(1 + 1 / n + (fx - mx) ** 2 / sxx)
    low = np.clip(fyhat - 2 * se_pred, 0, None)
    high = np.clip(fyhat + 2 * se_pred, 0, None)
    fyhat = np.clip(fyhat, 0, None)

    future_index = _extend_index(ts.index, periods)
    return {
        "history": ts,
        "forecast": pd.Series(fyhat, index=future_index),
        "low": pd.Series(low, index=future_index),
        "high": pd.Series(high, index=future_index),
        "slope": float(slope), "r2": float(r2), "n": n,
        "growth_pct": _pct(y[0], y[-1]),
        "cagr": _cagr(y),
        "proj_growth_pct": _pct(y[-1], float(fyhat[-1])),
        "last": float(y[-1]), "proj_last": float(fyhat[-1]),
        "proj_total": float(np.sum(fyhat)),
    }


def _extend_index(index, periods: int) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    freq = pd.infer_freq(idx)
    if freq:
        return pd.date_range(idx[-1], periods=periods + 1, freq=freq)[1:]
    delta = (idx[-1] - idx[-2]) if len(idx) >= 2 else pd.Timedelta(days=30)
    return pd.DatetimeIndex([idx[-1] + delta * (i + 1) for i in range(periods)])


def _pct(a: float, b: float) -> float | None:
    return ((b - a) / abs(a) * 100) if a else None


def _cagr(y) -> float | None:
    """Crecimiento compuesto por período entre el primer y el último valor."""
    y = np.asarray(y, dtype=float)
    if len(y) < 2 or y[0] <= 0 or y[-1] <= 0:
        return None
    return ((y[-1] / y[0]) ** (1 / (len(y) - 1)) - 1) * 100


# ── Tendencia por ítem (productos que suben / bajan) ────────────────────────
def item_trends(df: pd.DataFrame, item_col: str, date_col: str,
                value_col: str | None, freq: str = "M", agg: str = "sum",
                min_periods: int = 3) -> pd.DataFrame | None:
    """Por ítem: total, cambio % (1ª mitad vs 2ª mitad del histórico), pendiente
    y dirección. Base para 'qué productos suben/bajan sus ventas'."""
    if item_col not in df.columns or date_col not in df.columns:
        return None
    cols = [item_col, date_col] + ([value_col] if value_col and value_col in df.columns else [])
    work = df[cols].copy()
    work[date_col] = _to_dt(work[date_col])
    work = work.dropna(subset=[date_col, item_col])
    if work.empty:
        return None
    rule = _FREQ_RULE.get(freq, "MS")
    rows = []
    for item, g in work.groupby(item_col):
        g = g.set_index(date_col).sort_index()
        if value_col and value_col in df.columns:
            fn = agg if agg in ("sum", "mean", "max", "min") else "sum"
            ts = getattr(g[value_col].resample(rule), fn)()
        else:
            ts = g.resample(rule).size()
        ts = ts.fillna(0.0)
        if len(ts) < min_periods:
            continue
        y = ts.values.astype(float)
        slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])
        half = max(len(y) // 2, 1)
        first, last = y[:half].mean(), y[-half:].mean()
        change = _pct(first, last)
        rows.append({item_col: str(item), "total": float(y.sum()),
                     "cambio_pct": change if change is not None else 0.0,
                     "pendiente": slope})
    if not rows:
        return None
    out = pd.DataFrame(rows)
    out["direccion"] = np.where(out["cambio_pct"] > 8, "▲ subiendo",
                        np.where(out["cambio_pct"] < -8, "▼ bajando", "≈ estable"))
    return out


# ── Resúmenes en lenguaje natural ───────────────────────────────────────────
def _fmt(v, lang: str = "es") -> str:
    try:
        if v is None:
            return "n/a" if lang == "en" else "s/d"
        return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.1f}"
    except Exception:
        return str(v)


def forecast_summary(r: dict, label: str, freq: str, periods: int,
                     filtros: dict | None = None, lang: str = "es") -> str:
    if lang == "en":
        per = _FREQ_LABEL_PL_EN.get(freq, "periods")
        per_one = _FREQ_LABEL_EN.get(freq, "period")
        filtro_txt = ""
        if filtros:
            filtro_txt = " (" + ", ".join(
                f"{L.pretty(k, lang='en')}={v}" for k, v in filtros.items()
            ) + ")"
        trend = ("upward" if r["slope"] > 0 else
                 "downward" if r["slope"] < 0 else "flat")
        parts = [f"Forecast for {label}{filtro_txt} over the next {periods} {per}: "
                 f"{trend} trend."]
        if r.get("proj_growth_pct") is not None:
            signo = "+" if r["proj_growth_pct"] >= 0 else ""
            parts.append(
                f"I expect {_fmt(r['last'], lang)} → {_fmt(r['proj_last'], lang)} "
                f"per {per_one} ({signo}{r['proj_growth_pct']:.1f}%)."
            )
        if r.get("cagr") is not None:
            parts.append(f"Historical CAGR: {r['cagr']:+.1f}% per {per_one}.")
        parts.append(f"Projected total over the horizon: ~{_fmt(r['proj_total'], lang)}.")
        conf = ("high" if r["r2"] >= 0.7 else "medium" if r["r2"] >= 0.4 else "low")
        parts.append(
            f"Fit confidence: {conf} (R²={r['r2']:.2f}); "
            f"the shaded band is the likely range."
        )
        return " ".join(parts)

    per = _FREQ_LABEL_PL.get(freq, "períodos")
    filtro_txt = ""
    if filtros:
        filtro_txt = " (" + ", ".join(f"{L.pretty(k)}={v}" for k, v in filtros.items()) + ")"
    tendencia = ("al alza" if r["slope"] > 0 else
                 "a la baja" if r["slope"] < 0 else "plana")
    partes = [f"Proyección de {label}{filtro_txt} para los próximos {periods} {per}: "
              f"tendencia {tendencia}."]
    if r.get("proj_growth_pct") is not None:
        signo = "+" if r["proj_growth_pct"] >= 0 else ""
        partes.append(f"Estimo pasar de {_fmt(r['last'])} a {_fmt(r['proj_last'])} "
                      f"por {_FREQ_LABEL.get(freq, 'período')} ({signo}{r['proj_growth_pct']:.1f}%).")
    if r.get("cagr") is not None:
        partes.append(f"Crecimiento compuesto histórico: {r['cagr']:+.1f}% por "
                      f"{_FREQ_LABEL.get(freq, 'período')}.")
    partes.append(f"Total proyectado en el horizonte: ~{_fmt(r['proj_total'])}.")
    conf = ("alta" if r["r2"] >= 0.7 else "media" if r["r2"] >= 0.4 else "baja")
    partes.append(f"Confianza del ajuste: {conf} (R²={r['r2']:.2f}); "
                  f"la banda sombreada es el rango probable.")
    return " ".join(partes)


def trends_summary(trends: pd.DataFrame, item_col: str, rising: bool,
                   label: str | None = None, n: int = 5, lang: str = "es") -> str:
    metric = label or ("sales" if lang == "en" else "ventas")
    df = trends.sort_values("cambio_pct", ascending=not rising)
    df = df[df["cambio_pct"] > 0] if rising else df[df["cambio_pct"] < 0]
    if df.empty:
        if lang == "en":
            which = "rising" if rising else "declining"
            return f"No clearly {which} products in {metric} with the history available."
        cual = "en alza" if rising else "en caída"
        return f"No hay productos claramente {cual} en {metric} con la historia disponible."
    top = df.head(n)
    if lang == "en":
        verb = "rising" if rising else "declining"
        items = "; ".join(
            f"“{r[item_col]}” ({r['cambio_pct']:+.0f}%)" for _, r in top.iterrows()
        )
        return (f"Products {verb} in {metric} "
                f"(1st vs 2nd half of history): {items}.")
    verbo = "subiendo" if rising else "bajando"
    items = "; ".join(f"«{r[item_col]}» ({r['cambio_pct']:+.0f}%)" for _, r in top.iterrows())
    return (f"Productos {verbo} en {metric} "
            f"(cambio 1ª vs 2ª mitad del histórico): {items}.")
