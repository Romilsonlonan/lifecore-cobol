#!/usr/bin/env bash
# ================================================================
# SCRIPT  : run-cycle.sh
# DESCRICAO: Executa o ciclo batch diario do LifeCore-Mainframe
#            usando os binarios GnuCOBOL + arquivos de teste.
#            Simula o fluxo do JCL LCDIA01 localmente.
#
# USO:
#   ./SCRIPTS/run-cycle.sh          -- roda com dados de teste OK
#   ./SCRIPTS/run-cycle.sh erros    -- roda com dados contendo falhas
#   ./SCRIPTS/run-cycle.sh s0c7     -- provoca abend S0C7 proposital
# ================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LOAD_DIR="$ROOT_DIR/LOAD"
DATA_DIR="$ROOT_DIR/DATA"
TEST_DIR="$ROOT_DIR/TESTDATA"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

step_ok()   { echo -e "${GREEN}[STEP OK]${NC}  $1 RC=$2"; }
step_fail() { echo -e "${RED}[STEP ERR]${NC} $1 RC=$2"; }
step_warn() { echo -e "${YELLOW}[STEP WARN]${NC} $1 RC=$2"; }

run_step() {
    local step="$1"; local prog="$2"; shift 2
    local bin="$LOAD_DIR/$prog"
    if [[ ! -x "$bin" ]]; then
        echo -e "${YELLOW}[SKIP]${NC}     $step ($prog nao compilado)"
        return 0
    fi
    "$bin" "$@"
    local rc=$?
    if   [[ $rc -eq 0 ]]; then step_ok   "$step" $rc
    elif [[ $rc -eq 4 ]]; then step_warn "$step" $rc
    else                        step_fail "$step" $rc; fi
    return $rc
}

# ----------------------------------------------------------------
MODE="${1:-ok}"

echo "================================================================"
echo "  LifeCore-Mainframe — Ciclo Batch Diario"
echo "  Modo: $MODE"
echo "================================================================"
echo ""

# Escolhe arquivo de entrada
case "$MODE" in
    erros)  INPUT_APO="$TEST_DIR/APOLICE_ERROS.DAT" ;;
    s0c7)   INPUT_APO="$TEST_DIR/APOLICE_S0C7.DAT"  ;;
    *)      INPUT_APO="$TEST_DIR/APOLICE_OK.DAT"    ;;
esac

# Prepara ambiente de dados
mkdir -p "$DATA_DIR/INPUT" "$DATA_DIR/OUTPUT" "$DATA_DIR/QUARANTINE"
cp "$INPUT_APO"                     "$DATA_DIR/INPUT/APOLICE"
cp "$TEST_DIR/PAGAMENTO_OK.DAT"     "$DATA_DIR/INPUT/PAGAMENTO"
: > "$DATA_DIR/OUTPUT/APOLICE"
: > "$DATA_DIR/OUTPUT/FATURA"
: > "$DATA_DIR/OUTPUT/PAGAMENTO"
: > "$DATA_DIR/OUTPUT/CONCILIACAO"
: > "$DATA_DIR/QUARANTINE/APOLICE"

echo "STEP010 — ARQVAL01 (Validacao de Apolices)"
export LIFECORE_DATA_INPUT_APOLICE="$DATA_DIR/INPUT/APOLICE"
export LIFECORE_DATA_OUTPUT_APOLICE="$DATA_DIR/OUTPUT/APOLICE"
export LIFECORE_DATA_QUARANTINE_APOLICE="$DATA_DIR/QUARANTINE/APOLICE"
run_step STEP010 ARQVAL01 || true

echo ""
echo "STEP020 — VGCCAP01 (Calculo de Capital)"
export LIFECORE_DATA_OUTPUT_CAPITAL="$DATA_DIR/OUTPUT/CAPITAL"
run_step STEP020 VGCCAP01 || true

echo ""
echo "STEP030 — FATURA01 (Geracao de Faturamento)"
run_step STEP030 FATURA01 || true

echo ""
echo "STEP040 — PAGTO01 (Baixa de Pagamentos)"
export LIFECORE_DATA_INPUT_PAGAMENTO="$DATA_DIR/INPUT/PAGAMENTO"
export LIFECORE_DATA_OUTPUT_PAGAMENTO="$DATA_DIR/OUTPUT/PAGAMENTO"
run_step STEP040 PAGTO01 || true

echo ""
echo "STEP050 — CONCIL01 (Conciliacao Fatura x Pagamento)"
export LIFECORE_DATA_OUTPUT_CONCILIACAO="$DATA_DIR/OUTPUT/CONCILIACAO"
run_step STEP050 CONCIL01 || true

echo ""
echo "STEP060 — COMIS01 (Calculo de Comissoes)"
export LIFECORE_DATA_OUTPUT_COMISSAO="$DATA_DIR/OUTPUT/COMISSAO"
run_step STEP060 COMIS01 || true

echo ""
echo "================================================================"
echo "  RELATORIO FINAL"
echo "================================================================"
for f in APOLICE FATURA PAGAMENTO CONCILIACAO COMISSAO; do
    if [[ -f "$DATA_DIR/OUTPUT/$f" ]]; then
        count=$(grep -c "^D" "$DATA_DIR/OUTPUT/$f" 2>/dev/null || echo 0)
        echo "  $f: $count registros de detalhe"
    fi
done
QUAR=$(grep -c "^D" "$DATA_DIR/QUARANTINE/APOLICE" 2>/dev/null || echo 0)
echo "  QUARENTENA: $QUAR registros"
echo "================================================================"
