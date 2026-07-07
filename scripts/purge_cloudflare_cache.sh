#!/bin/sh
# Purge Cloudflare edge cache after deploy (optional).
# Requires: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID
# Optional: TRADEFLOW_PUBLIC_ORIGIN (default https://tradeflowcolon.com)
set -e

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] || [ -z "${CLOUDFLARE_ZONE_ID:-}" ]; then
  echo "[cloudflare] skip purge — CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID not set"
  exit 0
fi

ORIGIN="${TRADEFLOW_PUBLIC_ORIGIN:-https://tradeflowcolon.com}"
ORIGIN="${ORIGIN%/}"

# HTML /login/ (DYNAMIC but purge clears any stale edge rules) + static CSS/JS prefixes.
PAYLOAD=$(cat <<EOF
{
  "files": [
    "${ORIGIN}/login/"
  ],
  "prefixes": [
    "${ORIGIN}/static/css/",
    "${ORIGIN}/static/js/"
  ]
}
EOF
)

echo "[cloudflare] purging ${ORIGIN}/login/ and /static/css|js/ …"
HTTP_CODE=$(curl -sS -o /tmp/cf-purge.json -w '%{http_code}' \
  -X POST "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "${PAYLOAD}")

if [ "$HTTP_CODE" != "200" ]; then
  echo "[cloudflare] purge failed HTTP ${HTTP_CODE}"
  cat /tmp/cf-purge.json
  exit 1
fi

if ! grep -q '"success":true' /tmp/cf-purge.json; then
  echo "[cloudflare] purge API returned success=false"
  cat /tmp/cf-purge.json
  exit 1
fi

echo "[cloudflare] purge OK"
