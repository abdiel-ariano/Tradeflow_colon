from __future__ import annotations
import io
import pandas as pd


def _excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte tipos que xlsxwriter no soporta (datetimes con zona horaria,
    dict/list de jsonb, UUID, bytea) a algo escribible. Necesario para datos de
    Supabase/PostgreSQL."""
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if isinstance(s.dtype, pd.DatetimeTZDtype):
            df[col] = s.dt.tz_localize(None)
        elif s.dtype == object:
            df[col] = s.map(
                lambda v: v if (v is None or isinstance(v, (str, int, float, bool)))
                else str(v)
            )
    return df


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def to_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Export multiple DataFrames as sheets in a single Excel file."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#0F2A44",
            "font_color": "#ffffff",
            "border": 1,
        })
        for sheet_name, df in sheets.items():
            df = _excel_safe(df)
            safe_name = (sheet_name[:31] or "Hoja")
            df.to_excel(writer, sheet_name=safe_name, index=False, startrow=1, header=False)
            worksheet = writer.sheets[safe_name]
            for col_num, col_val in enumerate(df.columns):
                worksheet.write(0, col_num, str(col_val), header_fmt)
            for i, col in enumerate(df.columns):
                try:
                    max_len = max(int(df[col].astype(str).map(len).max()), len(str(col))) + 2
                except Exception:
                    max_len = len(str(col)) + 2
                worksheet.set_column(i, i, min(max_len, 40))
    return buffer.getvalue()
