#!/bin/sh
# Railway: migrate then gunicorn. PORT must be numeric (Railway injects it at runtime).
set -e

# Some Railway/custom start commands pass the literal "$PORT" without shell expansion.
_raw_port="${PORT:-8080}"
case "$_raw_port" in
  '$PORT'|"\$PORT"|"") _raw_port=8080 ;;
esac
# Keep digits only (defensive).
PORT="$(printf '%s' "$_raw_port" | tr -cd '0-9')"
if [ -z "$PORT" ]; then
  PORT=8080
fi
export PORT

echo "[tradeflow] PORT=${PORT}"
echo "[tradeflow] migrate --noinput"
python manage.py migrate --noinput

echo "[tradeflow] gunicorn 0.0.0.0:${PORT}"
exec gunicorn tradeflow_colon.wsgi \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
