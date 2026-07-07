#!/bin/sh
# Railway: verify database, migrate, then start gunicorn.
set -e

_raw_port="${PORT:-8080}"
case "$_raw_port" in
  '$PORT'|"\$PORT"|"") _raw_port=8080 ;;
esac
PORT="$(printf '%s' "$_raw_port" | tr -cd '0-9')"
if [ -z "$PORT" ]; then
  PORT=8080
fi
export PORT

if [ -z "${SECRET_KEY:-}" ] || [ "$SECRET_KEY" = "collectstatic-build-only-not-for-runtime" ]; then
  echo "[tradeflow] FATAL: define SECRET_KEY en Railway → Variables (no usar la clave dummy del build)."
  exit 1
fi

echo "[tradeflow] PORT=${PORT} ALLOWED_HOSTS=${ALLOWED_HOSTS:-<unset>} DATABASE_URL=${DATABASE_URL:+set}"

if [ "${SKIP_DB_PREFLIGHT:-false}" != "true" ]; then
  echo "[tradeflow] database preflight (check_database)..."
  if ! python manage.py check_database --quiet; then
    echo "[tradeflow] FATAL: database preflight failed — deploy aborted."
    echo "[tradeflow] Fix DATABASE_URL in Railway Variables (Supabase password / pooler user)."
    exit 1
  fi
  echo "[tradeflow] database preflight OK"
fi

echo "[tradeflow] migrate --noinput"
if python manage.py migrate --noinput; then
  echo "[tradeflow] migrate OK"
  if [ "${USE_DB_CACHE:-false}" = "true" ]; then
    echo "[tradeflow] createcachetable (USE_DB_CACHE)"
    python manage.py createcachetable --noinput 2>/dev/null || true
  fi
else
  echo "[tradeflow] FATAL: migrate failed — deploy aborted."
  exit 1
fi

if [ -x scripts/purge_cloudflare_cache.sh ]; then
  echo "[tradeflow] cloudflare cache purge (optional)"
  scripts/purge_cloudflare_cache.sh || echo "[tradeflow] WARN: cloudflare purge failed (non-fatal)"
fi

echo "[tradeflow] gunicorn 0.0.0.0:${PORT}"
exec gunicorn tradeflow_colon.wsgi \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
