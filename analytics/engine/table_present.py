"""Presentation helpers for Analytics tables (pandas → semantic HTML).

Keeps the DataFrame engine untouched: formats only the display edge for
seller/staff dashboards and chat bubbles in the CFZ marketplace UI.
"""
from __future__ import annotations
import re
from html import escape

import pandas as pd
from django.utils.safestring import mark_safe


def _is_delta_series(s: pd.Series) -> bool:
    """True when most non-null values look like percentage deltas (+12%)."""
    if s.dtype == object or str(s.dtype).startswith("string"):
        sample = s.dropna().astype(str).head(20)
        if sample.empty:
            return False
        return bool(sample.map(lambda v: bool(re.match(r"^[+\-]?\d+(\.\d+)?%$", v.strip()))).mean() > 0.6)
    return False


def _is_numeric_look(s: pd.Series) -> bool:
    """True for numeric dtypes or string cells that look like money/percents."""
    if pd.api.types.is_numeric_dtype(s):
        return True
    sample = s.dropna().astype(str).head(20)
    if sample.empty:
        return False
    return bool(sample.map(lambda v: bool(re.match(r"^\$?-?\d[\d,]*(\.\d+)?%?$", v.strip()))).mean() > 0.7)


def _cell(val, delta: bool = False) -> str:
    """Escape a cell; wrap delta values with up/down/flat tone spans."""
    text = "" if val is None or (isinstance(val, float) and pd.isna(val)) else str(val)
    if not delta:
        return escape(text)
    raw = text.strip()
    tone = "flat"
    if raw.startswith("+"):
        tone = "up"
    elif raw.startswith("-"):
        tone = "down"
    return f'<span class="an-delta an-delta-{tone}">{escape(raw)}</span>'


def dataframe_html(
    df: pd.DataFrame,
    *,
    classes: str = "tf-table an-data-table",
    delta_cols: list[str] | None = None,
    max_rows: int = 200,
) -> str:
    """Render a DataFrame as a compact, semantic HTML table for dashboards."""
    if df is None or df.empty:
        return ""
    view = df.head(int(max_rows)).copy()
    delta_set = set(delta_cols or [])
    for col in view.columns:
        if col in delta_set or _is_delta_series(view[col]):
            delta_set.add(col)

    numeric_set = {
        c for c in view.columns
        if c not in delta_set and _is_numeric_look(view[c])
    }

    parts = [f'<table class="{escape(classes)}" border="0">', "<thead><tr>"]
    for c in view.columns:
        cls = []
        if c in numeric_set or c in delta_set:
            cls.append("is-num")
        parts.append(f'<th class="{" ".join(cls)}">{escape(str(c))}</th>' if cls
                     else f"<th>{escape(str(c))}</th>")
    parts.append("</tr></thead><tbody>")

    for _, row in view.iterrows():
        parts.append("<tr>")
        for c in view.columns:
            is_delta = c in delta_set
            is_num = c in numeric_set or is_delta
            td_cls = ' class="is-num"' if is_num else ""
            parts.append(f"<td{td_cls}>{_cell(row[c], delta=is_delta)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    # Cells/headers already html.escape'd — SafeString avoids template |safe.
    return mark_safe("".join(parts))
