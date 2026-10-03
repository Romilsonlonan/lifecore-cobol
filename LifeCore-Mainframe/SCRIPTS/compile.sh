#!/usr/bin/env bash
# ================================================================
# SCRIPT  : compile.sh
# DESCRICAO: Compila todos os programas COBOL do LifeCore-Mainframe
#            usando GnuCOBOL (cobc) com suporte a ocesql (DB2 emulado
#            via PostgreSQL).
#
# PRE-REQUISITOS:
#   - GnuCOBOL 3.x    : sudo apt install gnucobol   (Debian/Ubuntu)
#   -                 : sudo dnf install gnucobol   (Fedora/RHEL)
#   - ocesql          : https://github.com/opensourcecobol/Open-COBOL-ESQL
#   - PostgreSQL       : sudo apt install postgresql
#
# USO:
#   ./SCRIPTS/compile.sh [programa]   -- compila um programa especifico
#   ./SCRIPTS/compile.sh all          -- compila todos
#   ./SCRIPTS/compile.sh check        -- verifica pre-requisitos
#
# AMBIENTE:
#   Esta implementacao usa GnuCOBOL + PostgreSQL como substituto
#   do DB2 z/OS para desenvolvimento local. No IBM Z Xplore, use
#   JCL com IKJEFT01 + DB2 real conforme LCDIA01.jcl.
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$ROOT_DIR/SRC/COBOL"
COPY_DIR="$ROOT_DIR/COPYLIB"
LOAD_DIR="$ROOT_DIR/LOAD"
DATA_DIR="$ROOT_DIR/DATA"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

mkdir -p "$LOAD_DIR"
mkdir -p "$DATA_DIR/INPUT" "$DATA_DIR/OUTPUT" "$DATA_DIR/QUARANTINE"

log_ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
log_err()  { echo -e "${RED}[ERRO]${NC}  $1"; }
log_warn() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
log_info() { echo -e "        $1"; }

# ----------------------------------------------------------------
check_prereqs() {
    echo "=== Verificando pre-requisitos ==="
    local ok=true

    if command -v cobc &>/dev/null; then
        log_ok "GnuCOBOL: $(cobc --version | head -1)"
    else
        log_err "GnuCOBOL nao encontrado. Instale com: sudo apt install gnucobol"
        ok=false
    fi

    if command -v ocesql &>/dev/null; then
        log_ok "ocesql: $(ocesql --version 2>&1 | head -1)"
    else
        log_warn "ocesql nao encontrado. Programas com EXEC SQL nao compilarao."
        log_info "Instale: https://github.com/opensourcecobol/Open-COBOL-ESQL"
    fi

    if command -v psql &>/dev/null; then
        log_ok "PostgreSQL client: $(psql --version)"
    else
        log_warn "psql nao encontrado. Carga do schema.sql nao funcionara."
    fi

    $ok && log_ok "Todos os pre-requisitos principais presentes." || true
    echo ""
}

# ----------------------------------------------------------------
# Programas sem EXEC SQL (compilacao direta com cobc)
compile_plain() {
    local prog="$1"
    local src="$SRC_DIR/${prog}.cbl"
    local out="$LOAD_DIR/${prog}"

    if [[ ! -f "$src" ]]; then
        log_err "Fonte nao encontrado: $src"
        return 1
    fi

    echo ">>> Compilando $prog (fixed-format COBOL)..."
    if cobc -x \
        -I "$COPY_DIR" \
        -o "$out" \
        "$src" 2>&1; then
        log_ok "$prog -> $LOAD_DIR/${prog}"
    else
        log_err "$prog falhou na compilacao"
        return 1
    fi
}

# ----------------------------------------------------------------
# Programas com EXEC SQL (pre-processamento ocesql + cobc)
compile_esql() {
    local prog="$1"
    local src="$SRC_DIR/${prog}.cbl"
    local preprocessed="$LOAD_DIR/${prog}_pp.cbl"
    local out="$LOAD_DIR/${prog}"

    if [[ ! -f "$src" ]]; then
        log_err "Fonte nao encontrado: $src"
        return 1
    fi

    if ! command -v ocesql &>/dev/null; then
        log_warn "$prog requer ocesql (nao instalado). Pulando."
        return 0
    fi

    echo ">>> Pre-processando $prog (ocesql)..."
    if ocesql "$src" "$preprocessed" 2>&1; then
        echo ">>> Compilando $prog (fixed-format COBOL + SQL)..."
        if cobc -x \
            -I "$COPY_DIR" \
            -locesql \
            -o "$out" \
            "$preprocessed" 2>&1; then
            log_ok "$prog -> $LOAD_DIR/${prog}"
        else
            log_err "$prog falhou na compilacao COBOL"
            return 1
        fi
    else
        log_err "$prog falhou no pre-processamento ocesql"
        return 1
    fi
}

# ----------------------------------------------------------------
compile_all() {
    echo "=== LifeCore-Mainframe — Compilacao Completa ==="
    echo ""

    # Programas sem SQL
    for prog in ARQVAL01 VGCCAP01 COMIS01 CLEAR01 SETTLE01; do
        compile_plain "$prog" || true
    done

    echo ""

    # Programas com EXEC SQL
    for prog in FATURA01 PAGTO01 CONCIL01 DISPUT01; do
        compile_esql "$prog" || true
    done

    echo ""
    echo "=== Resultado ==="
    ls -lh "$LOAD_DIR" 2>/dev/null || echo "(nenhum executavel gerado)"
}

# ----------------------------------------------------------------
compile_one() {
    local prog="${1^^}"  # uppercase
    case "$prog" in
        FATURA01|PAGTO01|CONCIL01|DISPUT01)
            compile_esql "$prog"
            ;;
        *)
            compile_plain "$prog"
            ;;
    esac
}

# ----------------------------------------------------------------
# MAIN
case "${1:-all}" in
    check)        check_prereqs ;;
    all)          check_prereqs; compile_all ;;
    *)            compile_one "$1" ;;
esac
