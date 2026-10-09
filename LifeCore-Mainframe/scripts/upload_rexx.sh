#!/bin/bash
# -----------------------------------------------------------------------
# upload_rexx.sh - Envia REXXs ao Hercules via card reader (porta 3505)
#                  Submete o JCL LCUPLOAD que ja tem todos os membros
# Uso: ./upload_rexx.sh
# -----------------------------------------------------------------------

HOST="127.0.0.1"
PORT="3505"
JCL="$(dirname "$0")/../JCL/LCUPLOAD.jcl"

echo "========================================"
echo " LifeCore IQ - Upload REXX via JCL"
echo " Submetendo: $JCL"
echo " Card reader: $HOST:$PORT"
echo "========================================"

if [ ! -f "$JCL" ]; then
  echo "[ERRO] JCL nao encontrado: $JCL"
  exit 1
fi

# Envia o JCL para o card reader do Hercules (porta 3505)
nc "$HOST" "$PORT" < "$JCL"

if [ $? -eq 0 ]; then
  echo ""
  echo "[OK] JCL enviado ao card reader!"
  echo ""
  echo "Agora no TSO verifique o job com:"
  echo "  STATUS LCUPLOAD"
  echo ""
  echo "Quando terminar (RC=0), execute:"
  echo "  EXEC 'HERC01.LIFECORE.REXX(LCLOGIN)'"
else
  echo "[ERRO] Falha ao enviar para o card reader."
  echo "Verifique se o Hercules esta rodando na porta $PORT"
  exit 1
fi
