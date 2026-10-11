#!/usr/bin/env bash
# =============================================================================
# upload_to_zos.sh — Envia todos os fontes do LifeCore IQ para o z/OS
#                    via porta 3505 (leitora de cartões do Hercules TK5R)
#
# Uso: ./LifeCore-Mainframe/SCRIPTS/upload_to_zos.sh
# Pré-req: nc (netcat) ou ncat instalado
# =============================================================================

set -euo pipefail

READER_HOST="${ZOS_HOST:-127.0.0.1}"
READER_PORT="${ZOS_PORT:-3505}"
BASE="LifeCore-Mainframe"
HLQ="LIFECORE"
USERID="HERC01"
DELAY="${UPLOAD_DELAY:-1}"   # segundos entre envios

# cores
GRN='\033[0;32m'; YEL='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

# verifica netcat
if command -v ncat &>/dev/null; then NC_CMD="ncat"
elif command -v nc &>/dev/null;  then NC_CMD="nc"
else echo -e "${RED}ERRO: netcat/ncat não encontrado. Instale: sudo dnf install ncat${NC}"; exit 1; fi

ok()   { echo -e "${GRN}  ✅  $1${NC}"; }
warn() { echo -e "${YEL}  ⚠   $1${NC}"; }
err()  { echo -e "${RED}  ❌  $1${NC}"; }

# --------------------------------------------------------------------------
# Função: submete um JCL/arquivo pela leitora 3505
# --------------------------------------------------------------------------
submit_jcl() {
    local file="$1"
    local label="$2"
    echo -e "${YEL}  → Enviando: $label${NC}"
    if $NC_CMD -w 3 "$READER_HOST" "$READER_PORT" < "$file" 2>/dev/null; then
        ok "$label enviado"
        sleep "$DELAY"
    else
        err "Falha ao enviar $label — leitora $READER_HOST:$READER_PORT acessível?"
    fi
}

# --------------------------------------------------------------------------
# Função: gera JCL de upload de um membro e submete
# Converte arquivo local em JCL com IEBUPDTE
# --------------------------------------------------------------------------
upload_member() {
    local src_file="$1"   # caminho local do arquivo
    local dsn="$2"         # ex: LIFECORE.SRC.COBOL
    local member="$3"      # ex: FATURA01

    local tmpjcl="/tmp/lc_upload_${member}.jcl"

    # gera JCL com IEBUPDTE para fazer upload do membro
    cat > "$tmpjcl" << ENDJCL
//UPL${member:0:6} JOB (LIFECORE),'UPLOAD ${member}',CLASS=A,MSGCLASS=H
//             NOTIFY=${USERID},MSGLEVEL=(1,1)
//UPLOAD   EXEC PGM=IEBUPDTE,PARM=NEW
//SYSPRINT DD  SYSOUT=*
//SYSUT2   DD  DSN=${dsn},
//             DISP=SHR
//SYSIN    DD  DATA,DLM='@@'
./ ADD NAME=${member}
ENDJCL

    # adiciona o conteúdo do arquivo (trunca em 72 cols, sem carregar lixo)
    while IFS= read -r line; do
        # garante 80 cols, substitui tabs por espaços
        printf '%-80s\n' "${line//	/ }" | cut -c1-80
    done < "$src_file" >> "$tmpjcl"

    # fecha o inline
    printf '\n@@\n' >> "$tmpjcl"

    submit_jcl "$tmpjcl" "${dsn}(${member})"
    rm -f "$tmpjcl"
}

# ==========================================================================
echo ""
echo "========================================================"
echo "  LifeCore IQ — Upload para z/OS (Hercules TK5R)"
echo "  Leitora: $READER_HOST:$READER_PORT"
echo "  HLQ:     $HLQ"
echo "========================================================"
echo ""

# --------------------------------------------------------------------------
# ETAPA 1 — Aloca todos os datasets (roda uma vez)
# --------------------------------------------------------------------------
echo "── ETAPA 1: Alocando datasets PDS ──────────────────────"
submit_jcl "$BASE/JCL/LCALLOC1.jcl" "LCALLOC1 (alocação de datasets)"
echo ""
echo "  Aguardando 5s para o job completar..."
sleep 5

# --------------------------------------------------------------------------
# ETAPA 2 — Upload dos fontes COBOL batch
# --------------------------------------------------------------------------
echo "── ETAPA 2: SRC.COBOL ──────────────────────────────────"
for f in "$BASE"/SRC/COBOL/*.cbl; do
    member=$(basename "$f" .cbl)
    upload_member "$f" "${HLQ}.SRC.COBOL" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 3 — Upload dos programas CICS
# --------------------------------------------------------------------------
echo "── ETAPA 3: SRC.CICS ───────────────────────────────────"
for f in "$BASE"/SRC/CICS/*.cbl; do
    member=$(basename "$f" .cbl)
    upload_member "$f" "${HLQ}.SRC.CICS" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 4 — Upload dos mapas BMS
# --------------------------------------------------------------------------
echo "── ETAPA 4: SRC.BMS ────────────────────────────────────"
for f in "$BASE"/SRC/BMS/*.bms; do
    member=$(basename "$f" .bms)
    upload_member "$f" "${HLQ}.SRC.BMS" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 5 — Upload dos copybooks
# --------------------------------------------------------------------------
echo "── ETAPA 5: COPYLIB ────────────────────────────────────"
for f in "$BASE"/COPYLIB/*.cpy; do
    member=$(basename "$f" .cpy)
    upload_member "$f" "${HLQ}.COPYLIB" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 6 — Upload dos JCLs
# --------------------------------------------------------------------------
echo "── ETAPA 6: JCL ────────────────────────────────────────"
for f in "$BASE"/JCL/*.jcl; do
    member=$(basename "$f" .jcl)
    upload_member "$f" "${HLQ}.JCL" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 7 — Upload dos REXX
# --------------------------------------------------------------------------
echo "── ETAPA 7: REXX ───────────────────────────────────────"
for f in "$BASE"/REXX/*.rexx; do
    member=$(basename "$f" .rexx)
    upload_member "$f" "${HLQ}.REXX" "$member"
done
echo ""

# --------------------------------------------------------------------------
# ETAPA 8 — Submete JCL de compilação COBOL batch
# --------------------------------------------------------------------------
echo "── ETAPA 8: Compilando COBOL batch ─────────────────────"
echo "  (use LCDIA01 para compilar depois — ou submeta LCSETUP1 no ISPF)"
echo ""

# --------------------------------------------------------------------------
echo "========================================================"
echo "  Upload concluído!"
echo ""
echo "  Próximos passos no ISPF:"
echo "  1. Opção 2 → DATA SET NAME ===> '${HLQ}.SRC.COBOL'"
echo "     → ver lista de membros COBOL"
echo "  2. Opção 2 → '${HLQ}.JCL' → S LCSETUP1 → compile"
echo "  3. Opção 5 (BATCH) → '${HLQ}.JCL(LCDIA01)' → rodar ciclo"
echo "  4. Transação CICS:  LCIN  → tela de login"
echo "========================================================"
