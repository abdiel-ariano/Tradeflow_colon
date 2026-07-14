import io
import json
import pandas as pd


def load_csv(file) -> pd.DataFrame:
    """Lee CSV tolerando codificación (UTF-8/BOM/latin-1) y separador
    (coma, punto y coma, tab, pipe)."""
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
    """Load all sheets from an Excel file. Returns {sheet_name: DataFrame}."""
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
    """Puntúa una hoja por cantidad de datos tabulares utilizables. Penaliza
    encabezados mal puestos (columnas 'Unnamed', típicas de pivotes/resúmenes
    con filas de título arriba)."""
    if df is None or df.empty:
        return -1
    unnamed = sum(1 for c in df.columns if str(c).startswith("Unnamed"))
    cells = int(df.notna().sum().sum())
    return cells - unnamed * 500


def load_excel(file) -> pd.DataFrame:
    """Carga la hoja con MÁS datos reales (ignora hojas vacías y prioriza tablas
    con encabezados correctos). Antes leía solo la primera hoja, que en archivos
    con varias hojas suele estar vacía o ser una portada."""
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
    """Nombres de las hojas con datos (omite vacías)."""
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
    """Nombre de la hoja con más datos tabulares (la que elige load_excel)."""
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
    """Carga una hoja específica por nombre."""
    return pd.read_excel(file, sheet_name=sheet)


def load_json(file) -> pd.DataFrame:
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
    """Parse pasted text: tries CSV comma, then semicolon, then tab."""
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
    """Light cleaning: normalize column names, infer numeric types."""
    df = df.copy()
    # Normalize column names: strip whitespace, lowercase, spaces → underscore
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    for col in df.columns:
        dtype = df[col].dtype
        # Skip booleans, numerics, datetimes — only try to convert object columns
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
