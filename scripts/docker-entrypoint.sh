#!/bin/sh
# Railway: bind gunicorn quickly; avoid collectstatic at runtime (done in Docker build).
set -e

PORT="${PORT:-8080}"

echo "[tradeflow] migrate --noinput"
python manage.py migrate --noinput

echo "[tradeflow] gunicorn 0.0.0.0:${PORT}"
exec gunicorn tradeflow_colon.wsgi \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
