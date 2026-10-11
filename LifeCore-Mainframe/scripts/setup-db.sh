#!/usr/bin/env bash
# ================================================================
# SCRIPT  : setup-db.sh
# DESCRICAO: Cria o banco PostgreSQL e aplica o schema do
#            LifeCore-Mainframe (substituto local do DB2 z/OS).
#
# USO:
#   ./SCRIPTS/setup-db.sh [create|drop|reset]
#
# PRE-REQUISITO: PostgreSQL rodando localmente
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA="$ROOT_DIR/SQL/schema.sql"

DB_NAME="${LIFECORE_DB_NAME:-lifecore}"
DB_USER="${LIFECORE_DB_USER:-postgres}"
DB_HOST="${LIFECORE_DB_HOST:-localhost}"
DB_PORT="${LIFECORE_DB_PORT:-5432}"

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERRO]${NC} $1"; exit 1; }

psql_run() {
    PGPASSWORD="${LIFECORE_DB_PASS:-}" \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$@"
}

case "${1:-create}" in
    create)
        echo "=== Criando banco $DB_NAME ==="
        psql_run -c "CREATE DATABASE $DB_NAME;" postgres 2>/dev/null \
            && ok "Banco $DB_NAME criado." \
            || echo "    (banco ja existe, continuando...)"
        echo "=== Aplicando schema ==="
        psql_run -d "$DB_NAME" -f "$SCHEMA"
        ok "Schema aplicado com sucesso."
        ;;
    drop)
        echo "=== Removendo banco $DB_NAME ==="
        psql_run -c "DROP DATABASE IF EXISTS $DB_NAME;" postgres
        ok "Banco $DB_NAME removido."
        ;;
    reset)
        "$0" drop
        "$0" create
        ;;
    *)
        err "Uso: $0 [create|drop|reset]"
        ;;
esac
