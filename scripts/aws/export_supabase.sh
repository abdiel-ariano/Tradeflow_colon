#!/usr/bin/env bash
# Create a private, verifiable logical backup of TradeFlow PostgreSQL.

set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly COUNTS_SQL="${SCRIPT_DIR}/critical_counts.sql"
readonly CREATED_AT="$(date -u +%Y%m%dT%H%M%SZ)"
readonly BACKUP_DIR="${1:-${PWD}/backups/supabase-${CREATED_AT}}"

require_command() {
    local command_name="$1"
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        printf 'ERROR: falta el comando %s.\n' "${command_name}" >&2
        exit 1
    fi
}

for command_name in pg_dump pg_restore psql sha256sum; do
    require_command "${command_name}"
done

: "${SOURCE_DB_HOST:?Define SOURCE_DB_HOST con el Session pooler de Supabase.}"
: "${SOURCE_DB_USER:?Define SOURCE_DB_USER, por ejemplo postgres.<project-ref>.}"

readonly SOURCE_DB_PORT="${SOURCE_DB_PORT:-5432}"
readonly SOURCE_DB_NAME="${SOURCE_DB_NAME:-postgres}"

if [[ -z "${SOURCE_DB_PASSWORD:-}" ]]; then
    read -r -s -p 'Contraseña de la base Supabase: ' SOURCE_DB_PASSWORD
    printf '\n'
fi

export PGPASSWORD="${SOURCE_DB_PASSWORD}"
trap 'unset PGPASSWORD SOURCE_DB_PASSWORD' EXIT

mkdir -p "${BACKUP_DIR}"
readonly DUMP_FILE="${BACKUP_DIR}/tradeflow-public.dump"
readonly COUNTS_FILE="${BACKUP_DIR}/source-counts.csv"
readonly MIGRATIONS_FILE="${BACKUP_DIR}/django-migrations.csv"
readonly MANIFEST_FILE="${BACKUP_DIR}/manifest.txt"

psql_source() {
    psql \
        --no-psqlrc \
        --set ON_ERROR_STOP=1 \
        --host "${SOURCE_DB_HOST}" \
        --port "${SOURCE_DB_PORT}" \
        --username "${SOURCE_DB_USER}" \
        --dbname "${SOURCE_DB_NAME}" \
        "$@"
}

readonly SERVER_VERSION_NUM="$(psql_source --tuples-only --no-align \
    --command 'SHOW server_version_num;' | tr -d '[:space:]')"
readonly SERVER_MAJOR="$((SERVER_VERSION_NUM / 10000))"
readonly CLIENT_MAJOR="$(pg_dump --version | sed -E 's/.* ([0-9]+)(\..*)?$/\1/')"

if (( CLIENT_MAJOR < SERVER_MAJOR )); then
    printf 'ERROR: pg_dump %s no puede respaldar PostgreSQL %s. Instala el cliente PostgreSQL %s.\n' \
        "${CLIENT_MAJOR}" "${SERVER_MAJOR}" "${SERVER_MAJOR}" >&2
    exit 1
fi

printf '[tradeflow] Verificando acceso a Supabase PostgreSQL %s...\n' "${SERVER_MAJOR}"
psql_source --quiet --command 'SELECT 1;' >/dev/null

printf '[tradeflow] Guardando conteos de control...\n'
psql_source --csv --file "${COUNTS_SQL}" >"${COUNTS_FILE}"
psql_source --csv --command \
    'SELECT app, name, applied FROM public.django_migrations ORDER BY app, name;' \
    >"${MIGRATIONS_FILE}"

printf '[tradeflow] Exportando únicamente el esquema public...\n'
pg_dump \
    --host "${SOURCE_DB_HOST}" \
    --port "${SOURCE_DB_PORT}" \
    --username "${SOURCE_DB_USER}" \
    --dbname "${SOURCE_DB_NAME}" \
    --format custom \
    --file "${DUMP_FILE}" \
    --schema public \
    --no-owner \
    --no-privileges \
    --lock-wait-timeout 10s

printf '[tradeflow] Validando el archivo generado...\n'
pg_restore --list "${DUMP_FILE}" >/dev/null

{
    printf 'created_at_utc=%s\n' "${CREATED_AT}"
    printf 'source_host=%s\n' "${SOURCE_DB_HOST}"
    printf 'source_database=%s\n' "${SOURCE_DB_NAME}"
    printf 'source_server_major=%s\n' "${SERVER_MAJOR}"
    printf 'pg_dump_major=%s\n' "${CLIENT_MAJOR}"
    printf 'dump_bytes=%s\n' "$(stat -c '%s' "${DUMP_FILE}")"
    sha256sum "${DUMP_FILE}"
    sha256sum "${COUNTS_FILE}"
    sha256sum "${MIGRATIONS_FILE}"
} >"${MANIFEST_FILE}"

printf '[tradeflow] Respaldo verificado: %s\n' "${BACKUP_DIR}"
printf '[tradeflow] SHA-256: %s\n' "$(sha256sum "${DUMP_FILE}" | cut -d' ' -f1)"
