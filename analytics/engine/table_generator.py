"""Table builders for seller analytics summaries and chat table specs.

Produces pandas views (stats, missingness, pivots, rankings) used by
export sheets and hybrid AI table replies for CFZ marketplace data.
"""
from __future__ import annotations
import pandas as pd
from typing import Optional


def raw_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return a defensive copy of the working dataset for export sheets."""
    return df.copy()


def statistics_table(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Describe numeric columns with business percentiles, or None if none."""
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return None
    stats = numeric.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).T
    stats.index.name = "columna"
    stats = stats.reset_index()
    return stats.round(4)


def _safe_nunique(s) -> int:
    """nunique that tolerates non-hashable jsonb dict/list cells."""
    try:
        return int(s.nunique(dropna=True))
    except TypeError:
        try:
            return int(s.astype(str).nunique(dropna=True))
        except Exception:
            return -1


def missing_values_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column null counts, null %, dtype, and unique-value counts."""
    total = len(df)
    missing = df.isnull().sum()
    pct = (missing / total * 100).round(2)
    dtypes = df.dtypes.astype(str)
    result = pd.DataFrame({
        "columna": df.columns,
        "tipo": dtypes.values,
        "valores_nulos": missing.values,
        "pct_nulo": pct.values,
        "valores_únicos": [_safe_nunique(df[c]) for c in df.columns],
    })
    return result


def frequency_table(df: pd.DataFrame, column: str, top_n: int = 20) -> pd.DataFrame:
    """Top-N value counts with share of rows for one categorical column."""
    counts = df[column].value_counts(dropna=False).head(top_n)
    pct = (counts / len(df) * 100).round(2)
    return pd.DataFrame({
        "valor": counts.index.astype(str),
        "frecuencia": counts.values,
        "porcentaje": pct.values,
    })


def correlation_table(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Pairwise numeric correlation matrix, or None if fewer than two cols."""
    numeric = df.select_dtypes(include="number")
    if numeric.shape[1] < 2:
        return None
    corr = numeric.corr().round(4)
    corr.index.name = "columna"
    return corr.reset_index()


def pivot_table(
    df: pd.DataFrame,
    index: str,
    columns: str,
    values: str,
    aggfunc: str = "sum",
) -> pd.DataFrame:
    """Build a filled pivot for seller chat/export cross-tabs."""
    agg_map = {
        "sum": "sum",
        "mean": "mean",
        "count": "count",
        "max": "max",
        "min": "min",
    }
    pivot = pd.pivot_table(
        df,
        index=index,
        columns=columns,
        values=values,
        aggfunc=agg_map.get(aggfunc, "sum"),
        fill_value=0,
    )
    pivot.columns = [str(c) for c in pivot.columns]
    return pivot.reset_index()


def groupby_table(
    df: pd.DataFrame,
    group_by: list[str],
    agg_col: str,
    aggfunc: str = "sum",
) -> pd.DataFrame:
    """Aggregate one metric by dimensions, sorted descending by the metric."""
    agg_map = {"sum": "sum", "mean": "mean", "count": "count", "max": "max", "min": "min"}
    fn = agg_map.get(aggfunc, "sum")
    result = df.groupby(group_by)[agg_col].agg(fn).reset_index()
    result.columns = group_by + [f"{aggfunc}_{agg_col}"]
    return result.sort_values(f"{aggfunc}_{agg_col}", ascending=False)


def ranked_table(df: pd.DataFrame, sort_by: str, ascending: bool = False) -> pd.DataFrame:
    """Sort rows and prepend a 1-based rank column for top-N style tables."""
    ranked = df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
    ranked.insert(0, "rank", ranked.index + 1)
    return ranked


def crosstab_table(df: pd.DataFrame, col1: str, col2: str) -> pd.DataFrame:
    """Two-way frequency table with TOTAL margins for chat crosstabs."""
    ct = pd.crosstab(df[col1], df[col2], margins=True, margins_name="TOTAL")
    ct.index.name = col1
    return ct.reset_index()


def transposed_table(df: pd.DataFrame) -> pd.DataFrame:
    """Transpose rows to columns as text (avoids Arrow mixed-type failures)."""
    t = df.T.reset_index()
    t.columns = ["campo"] + [f"fila_{i}" for i in range(len(df))]
    # Transposed rows mix text + numbers → force text for Arrow display.
    for c in t.columns[1:]:
        t[c] = t[c].astype(str)
    return t


def detect_categorical_columns(df: pd.DataFrame, max_unique_ratio: float = 0.5) -> list[str]:
    """Detect categorical columns across object, arrow str, category, bool.

    Low-cardinality numerics count; datetimes never; near-unique text
    (IDs/UUIDs) is excluded so auto-charts stay useful.
    """
    if df is None:
        return []
    result = []
    n = max(len(df), 1)
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            continue
        if pd.api.types.is_bool_dtype(s):
            result.append(col)
            continue
        try:
            nun = int(s.nunique(dropna=True))
        except TypeError:
            continue  # non-hashable jsonb dict/list: not categorical
        if nun == 0:
            continue  # fully empty column: nothing to chart
        if pd.api.types.is_numeric_dtype(s):
            if nun <= 30 and nun / n <= max_unique_ratio:
                result.append(col)
            continue
        # text / category
        if nun <= 50 or nun / n <= max_unique_ratio:
            result.append(col)
    return result


def detect_numeric_columns(df: pd.DataFrame) -> list[str]:
    """List numeric column names for KPI and chart selection."""
    if df is None:
        return []
    return list(df.select_dtypes(include="number").columns)
