#!/bin/sh
# Railway: gunicorn binds immediately; migrate runs in background.
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

(
  echo "[tradeflow] migrate --noinput (background)"
  if python manage.py migrate --noinput; then
    echo "[tradeflow] migrate OK"
  else
    echo "[tradeflow] WARN migrate failed (exit $?); gunicorn sigue activo"
  fi
) &

echo "[tradeflow] gunicorn 0.0.0.0:${PORT}"
exec gunicorn tradeflow_colon.wsgi \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
