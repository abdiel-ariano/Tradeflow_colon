"""File and paste loaders that normalize seller/staff analytics uploads.

Accepts CSV, Excel, JSON, and pasted text from CFZ ops exports and
light-cleans columns so charts and forecasts see consistent dtypes.
"""
import io
import json
import pandas as pd


def load_csv(file) -> pd.DataFrame:
    """Read CSV tolerating UTF-8/BOM/latin-1 and comma/;/tab/pipe separators."""
    raw = file.read() if hasattr(file, "read") else file
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    sample = text[:8000]
    counts = {sep: sample.count(sep) for sep in (",", ";", "\t", "|")}
    sep = max(counts, key=counts.get) if max(counts.values()) > 0 else ","
    return pd.read_csv(io.StringIO(text), sep=sep)


def load_excel_sheets(file) -> dict[str, pd.DataFrame]:
    """Load all non-empty Excel sheets as {sheet_name: DataFrame}."""
    xl = pd.ExcelFile(file)
    sheets = {}
    for name in xl.sheet_names:
        try:
            df = xl.parse(name)
            if not df.empty:
                sheets[name] = df
        except Exception:
            pass
    return sheets


def _sheet_score(df: pd.DataFrame) -> float:
    """Score a sheet by usable tabular cells; penalize Unnamed headers."""
    if df is None or df.empty:
        return -1
    unnamed = sum(1 for c in df.columns if str(c).startswith("Unnamed"))
    cells = int(df.notna().sum().sum())
    return cells - unnamed * 500


def load_excel(file) -> pd.DataFrame:
    """Load the sheet with the most real tabular data (skip empty covers)."""
    xl = pd.ExcelFile(file)
    best, best_score = None, -1.0
    for name in xl.sheet_names:
        try:
            df = xl.parse(name)
        except Exception:
            continue
        score = _sheet_score(df)
        if score > best_score:
            best, best_score = df, score
    if best is None or best.empty:
        raise ValueError("El Excel no tiene hojas con datos tabulares.")
    return best


def excel_sheet_names(file) -> list[str]:
    """Return names of sheets that contain at least one data row."""
    xl = pd.ExcelFile(file)
    out = []
    for name in xl.sheet_names:
        try:
            if not xl.parse(name).empty:
                out.append(name)
        except Exception:
            pass
    return out


def best_sheet_name(file) -> str | None:
    """Return the sheet name that load_excel would choose."""
    xl = pd.ExcelFile(file)
    best, score = None, -1.0
    for name in xl.sheet_names:
        try:
            s = _sheet_score(xl.parse(name))
        except Exception:
            continue
        if s > score:
            best, score = name, s
    return best


def load_excel_sheet(file, sheet: str) -> pd.DataFrame:
    """Load one Excel sheet by name into a DataFrame."""
    return pd.read_excel(file, sheet_name=sheet)


def load_json(file) -> pd.DataFrame:
    """Parse a JSON list or object into a flat DataFrame."""
    data = json.load(file)
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        try:
            return pd.DataFrame(data)
        except ValueError:
            return pd.json_normalize(data)
    raise ValueError("JSON debe ser una lista de objetos o un diccionario.")


def load_text(text: str) -> pd.DataFrame:
    """Parse pasted CSV-like text (comma, semicolon, tab, or pipe)."""
    text = text.strip()
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    raise ValueError(
        "No se pudo interpretar el texto. Usa formato CSV (coma, punto y coma, tab o pipe)."
    )


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Light clean: normalize column names and infer numeric object columns."""
    df = df.copy()
    # Normalize column names: strip, lowercase, spaces/hyphens → underscore
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    for col in df.columns:
        dtype = df[col].dtype
        # Skip booleans, numerics, datetimes — only try object columns
        if dtype != object:
            continue
        # Skip columns where values are not string-like (e.g. mixed bool/None)
        try:
            converted = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
        except Exception:
            continue
        non_null_original = df[col].notna().sum()
        if non_null_original == 0:
            continue
        if converted.notna().sum() / non_null_original > 0.7:
            df[col] = converted
    return df
