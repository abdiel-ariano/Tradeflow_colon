# Base de datos — TradeFlow Colón

## Resumen

TradeFlow usa **PostgreSQL** en entornos compartidos (Supabase, Railway, AWS RDS) y
**SQLite** en desarrollo local cuando no hay `DATABASE_URL`.

La configuración vive en `tradeflow_colon/settings.py` y se alimenta desde
`.env` (ver `.env.example`).

---

## Variables de entorno

| Variable | Obligatoria (prod) | Descripción |
|----------|-------------------|-------------|
| `DATABASE_URL` | Sí | URI `postgresql://…` |
| `DB_SSL` | Recomendado | `true` con Supabase/RDS |
| `DB_SSLMODE` | Recomendado | `require` |
| `SUPABASE_DB_HOST` | Alternativa | Si la URL tiene caracteres especiales en la contraseña |
| `SUPABASE_DB_PORT` | Alternativa | `5432` session o `6543` pooler |
| `SUPABASE_DB_PASSWORD` | Alternativa | Contraseña suelta |
| `SUPABASE_PROJECT_REF` | Alternativa | Corrige usuario del pooler |

---

## Arranque local

```bash
# Sin DATABASE_URL → SQLite en db.sqlite3
python manage.py migrate
python manage.py cargar_demo
```

## Arranque con Supabase

1. Copia la connection string del panel Supabase → Settings → Database.
2. Pégala en `DATABASE_URL` del `.env`.
3. Ejecuta:

```bash
python manage.py migrate
python manage.py cargar_demo
python manage.py verify_integrations
python manage.py check_database
```

**Pooler (Railway):** preferir puerto `6543` (transaction mode) para muchas
conexiones cortas de Gunicorn.

---

## Migraciones

- Generar: `python manage.py makemigrations`
- Aplicar: `python manage.py migrate`
- CI exige: `python manage.py makemigrations --check --dry-run`

Los modelos principales están en `core/models.py` y `core/enterprise_models.py`.

---

## Caché en base de datos

Si no hay Redis:

```env
USE_DB_CACHE=true
```

El entrypoint Docker puede ejecutar `createcachetable` cuando corresponda.

---

## Migración a AWS RDS

Plan detallado, scripts de export/import y verificación:

- [MIGRACION_DB_AWS_RDS.md](MIGRACION_DB_AWS_RDS.md)
- `scripts/aws/export_supabase.sh`
- `scripts/aws/restore_rds.sh`
- `scripts/aws/verify_migration.sh`

---

## Resolución de problemas

| Síntoma | Acción |
|---------|--------|
| `connection refused` | Revisar host/puerto y firewall Supabase |
| `password authentication failed` | URL-encode caracteres especiales o usar variables sueltas |
| Migrate cuelga | Validar `DATABASE_URL`; ver `check_database` |
| Datos vacíos en demo | `python manage.py cargar_demo` |

---

## Seguridad

- No commitear `.env` con credenciales reales.
- Usar roles de solo lectura solo para analytics externos, nunca para la app.
- Backups: política del proveedor (Supabase PITR / RDS snapshots).
