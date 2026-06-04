#!/usr/bin/env sh
# Railway web process: bind Gunicorn immediately (migrations run in release phase).
set -eu

PORT="${PORT:-8080}"
WORKERS="${WEB_CONCURRENCY:-1}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"

if [ -z "${SECRET_KEY:-}" ]; then
  echo "FATAL: SECRET_KEY is not set in Railway Variables." >&2
  exit 1
fi

echo "Starting Gunicorn on 0.0.0.0:${PORT} (workers=${WORKERS}, timeout=${TIMEOUT})"
exec gunicorn tradeflow_colon.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --threads 2 \
  --timeout "${TIMEOUT}" \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile -
