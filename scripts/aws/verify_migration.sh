#!/usr/bin/env bash
# Compare critical row counts after restoring TradeFlow into AWS RDS.

set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly COUNTS_SQL="${SCRIPT_DIR}/critical_counts.sql"
readonly SOURCE_COUNTS="${1:?Uso: verify_migration.sh RUTA_A_source-counts.csv}"

if [[ ! -f "${SOURCE_COUNTS}" ]]; then
    printf 'ERROR: no existe %s.\n' "${SOURCE_COUNTS}" >&2
    exit 1
fi

: "${TARGET_DB_HOST:?Define TARGET_DB_HOST.}"
: "${TARGET_DB_USER:?Define TARGET_DB_USER.}"

readonly TARGET_DB_PORT="${TARGET_DB_PORT:-5432}"
readonly TARGET_DB_NAME="${TARGET_DB_NAME:-tradeflow}"

if [[ -z "${TARGET_DB_PASSWORD:-}" ]]; then
    read -r -s -p 'Contraseña de la base RDS: ' TARGET_DB_PASSWORD
    printf '\n'
fi

export PGPASSWORD="${TARGET_DB_PASSWORD}"
readonly TARGET_COUNTS="$(mktemp)"
trap 'rm -f "${TARGET_COUNTS}"; unset PGPASSWORD TARGET_DB_PASSWORD' EXIT

psql \
    --no-psqlrc \
    --set ON_ERROR_STOP=1 \
    --host "${TARGET_DB_HOST}" \
    --port "${TARGET_DB_PORT}" \
    --username "${TARGET_DB_USER}" \
    --dbname "${TARGET_DB_NAME}" \
    --csv \
    --file "${COUNTS_SQL}" >"${TARGET_COUNTS}"

if ! diff --unified "${SOURCE_COUNTS}" "${TARGET_COUNTS}"; then
    printf 'ERROR: los conteos no coinciden. No conectes producción a RDS.\n' >&2
    exit 1
fi

psql \
    --no-psqlrc \
    --set ON_ERROR_STOP=1 \
    --host "${TARGET_DB_HOST}" \
    --port "${TARGET_DB_PORT}" \
    --username "${TARGET_DB_USER}" \
    --dbname "${TARGET_DB_NAME}" \
    --tuples-only \
    --no-align \
    --command "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public' AND p.proname = 'rls_auto_enable';" \
    | grep --quiet '^0$'

printf '[tradeflow] Verificación aprobada: conteos idénticos y sin función exclusiva de Supabase.\n'
