#!/usr/bin/env bash
# cobol_pci_hook.sh — LifeCore IQ
# Verifica fontes COBOL e copybooks em busca de:
#   1. Campos que armazenem PAN completo (violação PCI-DSS)
#   2. CPF hardcoded em WORKING-STORAGE
#   3. Variáveis suspeitas com nomes proibidos
#
# Uso: pre-commit run cobol-pci-check

set -euo pipefail

FAILED=0
FILES=("$@")

# Padrões proibidos: nome da variável sugere armazenamento de PAN
PAN_PATTERNS=(
  "NR-CARTAO-COMPLETO"
  "NUMERO-CARTAO"
  "PAN-COMPLETO"
  "CARD-NUMBER"
  "NR-PAN"
  "FULL-PAN"
)

# Padrões suspeitos de CPF hardcoded (sequências de 11 dígitos em FILLER/VALUE)
CPF_PATTERN='^[[:space:]]*[0-9][[:space:]]*VALUE[[:space:]]*['\''"]?[0-9]\{11\}'

for FILE in "${FILES[@]}"; do
  [[ -f "$FILE" ]] || continue

  # 1. Verificar campos PAN
  for PAT in "${PAN_PATTERNS[@]}"; do
    if grep -in "$PAT" "$FILE" > /dev/null 2>&1; then
      LINE=$(grep -in "$PAT" "$FILE" | head -1)
      echo "::error file=$FILE::PCI-DSS: campo PAN detectado — '$PAT' em: $LINE"
      FAILED=$((FAILED + 1))
    fi
  done

  # 2. Verificar CPF hardcoded em VALUE clause (11 dígitos seguidos)
  if grep -Pn "VALUE\s+['\"]?\d{11}['\"]?" "$FILE" 2>/dev/null | \
     grep -v "TESTDATA\|COMMENT\|^\*" > /dev/null 2>&1; then
    LINE=$(grep -Pn "VALUE\s+['\"]?\d{11}['\"]?" "$FILE" | head -1)
    echo "::warning file=$FILE::LGPD: possível CPF hardcoded em VALUE clause — $LINE"
  fi

  # 3. Verificar SQLCA inline (deve usar COPY CPYSQLCA)
  # Exclui o próprio CPYSQLCA.cpy que é a definição canônica
  BASENAME=$(basename "$FILE")
  if [[ "$BASENAME" != "CPYSQLCA.cpy" ]] && grep -in "05  SQLCAID" "$FILE" > /dev/null 2>&1; then
    echo "::error file=$FILE::Use COPY CPYSQLCA ao invés de SQLCA inline"
    FAILED=$((FAILED + 1))
  fi

done

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "🏦 COBOL PCI Check: $FAILED violação(ões) encontrada(s). Commit bloqueado."
  exit 1
fi

echo "✓ COBOL PCI check — nenhuma violação detectada."
exit 0
