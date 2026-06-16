#!/usr/bin/env bash
# Despliega send-transactional-email en Supabase (Gmail SMTP relay).
# Requisitos: Supabase CLI instalado y autenticado.
#
#   brew install supabase/tap/supabase   # macOS
#   npm i -g supabase                    # alternativa
#
# Uso:
#   export SUPABASE_ACCESS_TOKEN=sbp_...
#   export SUPABASE_PROJECT_REF=tu_ref
#   export GMAIL_USER=tradeflowcolon@gmail.com
#   export GMAIL_APP_PASSWORD=xxxx
#   bash scripts/deploy_supabase_email.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v supabase >/dev/null 2>&1; then
  echo "Instala Supabase CLI: https://supabase.com/docs/guides/cli"
  exit 1
fi

: "${SUPABASE_PROJECT_REF:?Define SUPABASE_PROJECT_REF (Reference ID en Supabase → Settings → General)}"

if [ -n "${SUPABASE_ACCESS_TOKEN:-}" ]; then
  export SUPABASE_ACCESS_TOKEN
fi

if [ -n "${GMAIL_USER:-}" ] && [ -n "${GMAIL_APP_PASSWORD:-}" ]; then
  echo "Configurando secrets en Supabase…"
  supabase secrets set --project-ref "$SUPABASE_PROJECT_REF" \
    GMAIL_USER="$GMAIL_USER" \
    GMAIL_APP_PASSWORD="$GMAIL_APP_PASSWORD" \
    ${DEFAULT_FROM_NAME:+DEFAULT_FROM_NAME="$DEFAULT_FROM_NAME"}
else
  echo "GMAIL_USER/GMAIL_APP_PASSWORD no en entorno; asumiendo secrets ya en Supabase Dashboard."
fi

echo "Desplegando send-transactional-email…"
supabase functions deploy send-transactional-email --project-ref "$SUPABASE_PROJECT_REF"

echo ""
echo "Listo. Prueba:"
echo "  curl -X POST \"https://${SUPABASE_PROJECT_REF}.supabase.co/functions/v1/send-transactional-email\" \\"
echo "    -H \"Authorization: Bearer TU_SERVICE_ROLE_KEY\" \\"
echo "    -H \"apikey: TU_SERVICE_ROLE_KEY\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"to\":\"tu@gmail.com\",\"subject\":\"Test\",\"html\":\"<p>OK</p>\",\"text\":\"OK\"}'"
