#!/usr/bin/env bash
# Restore a TradeFlow public-schema dump into an empty AWS RDS database.

set -Eeuo pipefail
umask 077

readonly DUMP_FILE="${1:?Uso: restore_rds.sh RUTA_AL_DUMP}"

require_command() {
    local command_name="$1"
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        printf 'ERROR: falta el comando %s.\n' "${command_name}" >&2
        exit 1
    fi
}

for command_name in pg_restore psql; do
    require_command "${command_name}"
done

if [[ ! -f "${DUMP_FILE}" ]]; then
    printf 'ERROR: no existe %s.\n' "${DUMP_FILE}" >&2
    exit 1
fi

: "${TARGET_DB_HOST:?Define TARGET_DB_HOST con el endpoint privado de RDS.}"
: "${TARGET_DB_USER:?Define TARGET_DB_USER.}"

readonly TARGET_DB_PORT="${TARGET_DB_PORT:-5432}"
readonly TARGET_DB_NAME="${TARGET_DB_NAME:-tradeflow}"

if [[ -z "${TARGET_DB_PASSWORD:-}" ]]; then
    read -r -s -p 'Contraseña de la base RDS: ' TARGET_DB_PASSWORD
    printf '\n'
fi

export PGPASSWORD="${TARGET_DB_PASSWORD}"
trap 'unset PGPASSWORD TARGET_DB_PASSWORD' EXIT

psql_target() {
    psql \
        --no-psqlrc \
        --set ON_ERROR_STOP=1 \
        --host "${TARGET_DB_HOST}" \
        --port "${TARGET_DB_PORT}" \
        --username "${TARGET_DB_USER}" \
        --dbname "${TARGET_DB_NAME}" \
        "$@"
}

readonly EXISTING_TABLES="$(psql_target --tuples-only --no-align --command \
    "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" | tr -d '[:space:]')"

if (( EXISTING_TABLES > 0 )); then
    printf 'ERROR: la base objetivo contiene %s tablas públicas. No se sobrescribirá.\n' \
        "${EXISTING_TABLES}" >&2
    printf 'Usa una base vacía para el ensayo o para el corte final.\n' >&2
    exit 1
fi

printf '[tradeflow] Restaurando en %s/%s...\n' "${TARGET_DB_HOST}" "${TARGET_DB_NAME}"
pg_restore \
    --host "${TARGET_DB_HOST}" \
    --port "${TARGET_DB_PORT}" \
    --username "${TARGET_DB_USER}" \
    --dbname "${TARGET_DB_NAME}" \
    --exit-on-error \
    --single-transaction \
    --no-owner \
    --no-privileges \
    "${DUMP_FILE}"

printf '[tradeflow] Retirando artefactos exclusivos de Supabase...\n'
psql_target --command 'DROP FUNCTION IF EXISTS public.rls_auto_enable();'

printf '[tradeflow] Instalando extensiones compatibles usadas por TradeFlow...\n'
psql_target --command 'CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;'
psql_target --command 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;'
psql_target --command 'ANALYZE;'

printf '[tradeflow] Restauración completada. Ejecuta verify_migration.sh antes de conectar Django.\n'
