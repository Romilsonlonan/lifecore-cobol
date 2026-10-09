#!/bin/bash
# =================================================================
# upload-rexx.sh — Faz upload dos programas REXX do LifeCore IQ
#                  para o MVS TK5R via c3270/x3270 scripting
#
# Pre-requisito: Hercules rodando + TSO logado em outro terminal
# Uso: bash upload-rexx.sh
# =================================================================

REXX_DIR="$(cd "$(dirname "$0")/../REXX" && pwd)"
MVS_DATASET="HERC01.LIFECORE.REXX"

echo "================================================================"
echo " LifeCore IQ — Upload de programas REXX para MVS TK5R"
echo "================================================================"
echo ""
echo "Dataset destino : $MVS_DATASET"
echo "Diretorio fonte : $REXX_DIR"
echo ""

# Verificar se Hercules esta rodando
if ! ss -tlnp | grep -q ':3270'; then
  echo "ERRO: Hercules nao esta rodando. Execute: herc-start"
  exit 1
fi

# Listar arquivos REXX
files=("LCLOGIN" "LCMENU" "LCESTIP" "LCFATUR" "LCBATCH")

echo "Arquivos a transferir:"
for f in "${files[@]}"; do
  if [ -f "$REXX_DIR/${f}.rexx" ]; then
    echo "  OK  $REXX_DIR/${f}.rexx -> $MVS_DATASET($f)"
  else
    echo "  NAO ENCONTRADO: $REXX_DIR/${f}.rexx"
  fi
done

echo ""
echo "Para transferir via TSO no c3270:"
echo ""
echo "  1. No TSO, primeiro aloque o dataset:"
echo "     ALLOC FI(RXLIB) DA('$MVS_DATASET') NEW CATALOG"
echo "     RECFM(F B) LRECL(80) BLKSIZE(3120) TRACKS SPACE(5 5) DIR(20)"
echo ""
echo "  2. Depois use IND\$FILE ou copie via editor ISPF (opcao 2)"
echo ""
echo "  ALTERNATIVA MAIS SIMPLES no TSO:"
echo "  Digite no prompt TSO:"
echo ""
echo "  TSO EXEC 'BREXX.INSTALL.SAMPLES(#TSOAPPL)'"
echo ""
echo "  Isso confirma que o BREXX FSS funciona."
echo ""
echo "  Para rodar o LifeCore diretamente (sem upload):"
echo "  Copie o conteudo de LCLOGIN.rexx no editor ISPF (opcao 2)"
echo ""

# Gerar arquivo de comandos para x3270
echo "Gerando script x3270 para upload automatico..."

cat > /tmp/lc-upload.x3270 << 'SCRIPT'
# x3270 script para criar dataset e fazer upload
# Uso: x3270 -script 127.0.0.1:3270 < /tmp/lc-upload.x3270
Wait(InputField)
String("TSO HERC01\n")
Wait(InputField)
String("CUL8TR\n")
Wait(InputField)
SCRIPT

echo "Script gerado: /tmp/lc-upload.x3270"
echo ""
echo "================================================================"
echo " INSTRUCAO MANUAL (mais confiavel):"
echo "================================================================"
echo ""
echo " No c3270 ja logado no TSO, digite:"
echo ""
echo "   ALLOC FI(RXLIB) DA('HERC01.LIFECORE.REXX') NEW CATALOG +"
echo "   RECFM(F B) LRECL(80) BLKSIZE(3120) TRACKS SPACE(5 5) DIR(20)"
echo ""
echo "   ISPF"
echo "   -> Opcao 2 (Edit)"
echo "   -> Dataset: HERC01.LIFECORE.REXX"
echo "   -> Membro  : LCLOGIN"
echo "   -> Cole o conteudo de LCLOGIN.rexx"
echo "   -> PF3 para salvar, repita para LCMENU, LCESTIP, LCFATUR, LCBATCH"
echo ""
echo "   Para executar:"
echo "   TSO EXEC 'HERC01.LIFECORE.REXX(LCLOGIN)'"
echo ""
