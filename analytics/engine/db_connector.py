"""Read-only DB connectors for Analytics IA (Postgres/Supabase, MySQL).

Dialect is inferred from the URI:

    postgresql://user:pass@host:5432/db      -> psycopg2
    mysql://user:pass@host:3306/db           -> pymysql

Each call opens and closes its own connection (stateless); only the
connection string is cached server-side. Used for staff multi-source loads.
"""
from __future__ import annotations
from urllib.parse import urlparse, unquote, quote
import pandas as pd

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None
try:
    import pymysql
except Exception:  # pragma: no cover
    pymysql = None

_SYS_SCHEMAS = ("pg_catalog", "information_schema")
_MYSQL_SYS = ("information_schema", "mysql", "performance_schema", "sys")
_TEXT_TYPES = ("character varying", "text", "character", "citext", "name",
               "varchar", "char", "tinytext", "mediumtext", "longtext", "enum")
_LABEL_PREFER = ("name", "nombre", "title", "titulo", "label", "email", "sku",
                 "code", "codigo", "descrip", "razon", "company", "empresa", "author")


def available() -> bool:
    """True when at least one DB driver (psycopg2 or pymysql) is installed."""
    return psycopg2 is not None or pymysql is not None


def normalize_conn_str(conn_str: str) -> str:
    """Percent-encode user/password so literal '@' in passwords parses correctly.

    Host is the segment after the last '@'; an unencoded '@' in the
    password would shift the host. Idempotent when already percent-encoded.
    """
    s = (conn_str or "").strip()
    if "://" not in s or "@" not in s:
        return s
    scheme, rest = s.split("://", 1)
    if "/" in rest:
        authority, path = rest.split("/", 1)
        path = "/" + path
    else:
        authority, path = rest, ""
    if "@" not in authority:
        return s
    # El host nunca contiene '@' → el último '@' de la autoridad es el delimitador
    # real, sin importar cuántos '@' traiga la contraseña.
    userinfo, hostport = authority.rsplit("@", 1)
    if ":" in userinfo:
        user, pwd = userinfo.split(":", 1)
        new_userinfo = f"{quote(unquote(user), safe='')}:{quote(unquote(pwd), safe='')}"
    else:
        new_userinfo = quote(unquote(userinfo), safe="")
    return f"{scheme}://{new_userinfo}@{hostport}{path}"


def _dialect(conn_str: str) -> str:
    """Return 'mysql' or 'postgres' from the connection URI scheme."""
    s = (conn_str or "").strip().lower()
    if s.startswith(("mysql://", "mysql+pymysql://", "mariadb://")):
        return "mysql"
    return "postgres"


def _mysql_db(conn_str: str) -> str:
    """Database name from a MySQL URI path."""
    return (urlparse(normalize_conn_str(conn_str)).path or "/").lstrip("/")


def _resolve_schema(conn_str: str, schema: str) -> str:
    """Map schema for MySQL (DB name) when callers pass Postgres 'public'."""
    if _dialect(conn_str) == "mysql" and (not schema or schema == "public"):
        return _mysql_db(conn_str)
    return schema or "public"


def _q(dialect: str, *idents: str) -> str:
    """Quote and join SQL identifiers for the active dialect."""
    ch = "`" if dialect == "mysql" else '"'
    return ".".join(f"{ch}{i}{ch}" for i in idents)


def _connect(conn_str: str):
    """Open a DB connection for the URI dialect (caller must close)."""
    s = normalize_conn_str(conn_str)
    if not s:
        raise ValueError("La cadena de conexión está vacía.")
    if _dialect(s) == "mysql":
        if pymysql is None:
            raise RuntimeError("Falta pymysql. Instala: pip install pymysql")
        u = urlparse(s)
        return pymysql.connect(
            host=u.hostname or "localhost", port=u.port or 3306,
            user=unquote(u.username or ""), password=unquote(u.password or ""),
            database=(u.path or "/").lstrip("/") or None, connect_timeout=15,
        )
    if psycopg2 is None:
        raise RuntimeError("Falta psycopg2. Instala: pip install psycopg2-binary")
    return psycopg2.connect(s, connect_timeout=15)


def _df(cur) -> pd.DataFrame:
    """Materialize the current cursor result set as a DataFrame."""
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)


def test_connection(conn_str: str) -> None:
    """Raise if the connection string cannot run SELECT 1."""
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()


def list_schemas(conn_str: str) -> list[str]:
    """List non-system schemas (or MySQL databases) available to the user."""
    dia = _dialect(conn_str)
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            if dia == "mysql":
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name NOT IN %s ORDER BY schema_name", (_MYSQL_SYS,))
            else:
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name NOT IN %s AND schema_name NOT LIKE 'pg\\_%%' "
                    "ORDER BY schema_name", (_SYS_SCHEMAS,))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_tables(conn_str: str, schema: str = "public") -> list[dict]:
    """List tables/views with approximate row counts: [{name, rows}]."""
    dia = _dialect(conn_str)
    schema = _resolve_schema(conn_str, schema)
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            if dia == "mysql":
                cur.execute(
                    "SELECT table_name, IFNULL(table_rows, 0) "
                    "FROM information_schema.tables WHERE table_schema = %s "
                    "ORDER BY table_name", (schema,))
            else:
                cur.execute(
                    "SELECT c.relname, GREATEST(c.reltuples, 0)::bigint "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m') "
                    "ORDER BY c.relname", (schema,))
            return [{"name": r[0], "rows": int(r[1])} for r in cur.fetchall()]
    finally:
        conn.close()


def list_foreign_keys(conn_str: str, schema: str = "public") -> list[dict]:
    """List FK edges as [{table, column, ref_table, ref_column}]."""
    dia = _dialect(conn_str)
    schema = _resolve_schema(conn_str, schema)
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            if dia == "mysql":
                cur.execute(
                    "SELECT table_name, column_name, referenced_table_name, "
                    "referenced_column_name FROM information_schema.key_column_usage "
                    "WHERE referenced_table_name IS NOT NULL AND table_schema = %s "
                    "ORDER BY table_name, column_name", (schema,))
            else:
                cur.execute(
                    """
                    SELECT tc.table_name, kcu.column_name,
                           ccu.table_name AS ref_table, ccu.column_name AS ref_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                      ON ccu.constraint_name = tc.constraint_name
                     AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
                    ORDER BY tc.table_name, kcu.column_name
                    """, (schema,))
            return [{"table": r[0], "column": r[1],
                     "ref_table": r[2], "ref_column": r[3]} for r in cur.fetchall()]
    finally:
        conn.close()


def _columns(conn_str: str, schema: str, table: str) -> list[dict]:
    """Return [{name, type}] for columns of one table."""
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (schema, table))
            return [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def _label_column(conn_str: str, schema: str, table: str, fallback: str) -> str:
    """Pick a human-friendly text column for JOIN enrichment labels."""
    cols = _columns(conn_str, schema, table)
    text_cols = [c["name"] for c in cols if c["type"] in _TEXT_TYPES]
    for pref in _LABEL_PREFER:
        for c in text_cols:
            if pref in c.lower():
                return c
    return text_cols[0] if text_cols else fallback


def read_table(conn_str: str, table: str, schema: str = "public",
               limit: int = 5000) -> pd.DataFrame:
    """SELECT * from a table/view capped at limit rows."""
    dia = _dialect(conn_str)
    schema = _resolve_schema(conn_str, schema)
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {_q(dia, schema, table)} LIMIT %s", (int(limit),))
            return _df(cur)
    finally:
        conn.close()


def read_table_joined(conn_str: str, table: str, schema: str = "public",
                      limit: int = 5000) -> pd.DataFrame:
    """Read a table with LEFT JOIN label columns from referenced FK tables."""
    dia = _dialect(conn_str)
    schema = _resolve_schema(conn_str, schema)
    fks = [fk for fk in list_foreign_keys(conn_str, schema) if fk["table"] == table]
    if not fks:
        return read_table(conn_str, table, schema, limit)

    selects, joins, used = ["b.*"], [], set()
    for i, fk in enumerate(fks):
        ref, refcol, col = fk["ref_table"], fk["ref_column"], fk["column"]
        label = _label_column(conn_str, schema, ref, refcol)
        base = col[:-3] if col.endswith("_id") else col
        out = f"{base}_{label}"
        while out in used:
            out += "_x"
        used.add(out)
        alias = f"r{i}"
        selects.append(f"{alias}.{_q(dia, label)} AS {_q(dia, out)}")
        joins.append(
            f"LEFT JOIN {_q(dia, schema, ref)} {alias} "
            f"ON b.{_q(dia, col)} = {alias}.{_q(dia, refcol)}")

    sql = (f"SELECT {', '.join(selects)} FROM {_q(dia, schema, table)} b "
           + " ".join(joins) + f" LIMIT {int(limit)}")
    conn = _connect(conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return _df(cur)
    finally:
        conn.close()


def run_query(conn_str: str, sql: str, max_rows: int = 20000) -> pd.DataFrame:
    """Run a read-only SQL statement and return at most max_rows as a DataFrame."""
    from core.utils.sql_guard import assert_readonly_sql

    sql = assert_readonly_sql(sql)
    dia = _dialect(conn_str)
    conn = _connect(conn_str)
    try:
        if dia == "postgres":
            conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return pd.DataFrame()
            return _df(cur).head(max_rows)
    finally:
        conn.close()
