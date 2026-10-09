"""
LifeCore AI Layer — Dataset de Fine-tuning
Gera pares (instrução, resposta) no formato ChatML/Alpaca/ShareGPT
a partir do RUNBOOK, copybooks e domain knowledge do LifeCore.

Formatos suportados:
  - alpaca   : {"instruction", "input", "output"}
  - sharegpt : {"conversations": [{"from": "human/gpt", "value": "..."}]}
  - chatml   : JSONL com system/user/assistant (compatível com Unsloth/TRL)

Uso:
  python -m app.ai.finetune.dataset --format chatml --output dataset.jsonl
  python -m app.ai.finetune.dataset --augment --output dataset_augmented.jsonl

Depois:
  # Fine-tuning com Unsloth (QLoRA, 4-bit, 1 GPU):
  # https://github.com/unslothai/unsloth
  unsloth finetune --model llama3.2-3b-4bit --data dataset.jsonl

  # Quantização após fine-tuning:
  # llama.cpp: ./quantize model.gguf model-q4_k_m.gguf Q4_K_M
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Literal

logger = logging.getLogger(__name__)

Format = Literal["alpaca", "sharegpt", "chatml"]

SYSTEM_PROMPT = (
    "Você é o assistente técnico do LifeCore-Mainframe, especializado em "
    "COBOL, z/OS, JCL, DB2, seguros de vida em grupo (VGC/GLB) e análise de abends. "
    "Responda em português (BR) com precisão técnica."
)

# ── Dataset base ──────────────────────────────────────────────────────────────
# Cada item: (instruction, input_context, gold_output)
# Expandir com exemplos reais do RUNBOOK e logs de produção

RAW_PAIRS: list[tuple[str, str, str]] = [
    # ── Abends ────────────────────────────────────────────────────────────────
    (
        "Explique o abend S0C7 e como corrigi-lo em um programa COBOL com campos COMP-3.",
        "Programa: FATURA01. Campo suspeito: VL-CAPITAL-SEGURADO PIC S9(11)V99 COMP-3.",
        (
            "O S0C7 (Data Exception) ocorre quando uma instrução aritmética ou MOVE "
            "encontra um campo COMP-3 (packed-decimal) com conteúdo inválido — bits "
            "de zona ou dígito fora do intervalo 0-9, ou sinal inválido.\n\n"
            "**No FATURA01:** o campo VL-CAPITAL-SEGURADO não foi inicializado antes "
            "do primeiro cálculo. Em COBOL, campos numéricos sem VALUE ficam com "
            "conteúdo de memória indefinido.\n\n"
            "**Correção:**\n"
            "1. Adicione `VALUE ZEROS` ou `VALUE 0` na declaração do campo.\n"
            "2. Execute ARQVAL01 antes do FATURA01 para validar os dados de entrada.\n"
            "3. No arquivo de teste APOLICE_S0C7.DAT há um caso intencional para "
            "reproduzir o problema.\n\n"
            "**No z/OS:** use IPCS para analisar o dump e identificar o offset exato."
        ),
    ),
    (
        "Como diagnosticar S0C4 em um programa COBOL que usa tabelas com OCCURS?",
        "",
        (
            "S0C4 (Protection Exception) indica acesso a endereço de memória inválido. "
            "Em programas com OCCURS, a causa mais comum é um subscrito fora dos limites.\n\n"
            "**Investigação:**\n"
            "1. Identifique o PSW no dump e calcule o offset.\n"
            "2. Verifique todos os subscritos (WS-IDX, WS-I) com valor > OCCURS.\n"
            "3. Confirme que o arquivo foi aberto com AT END antes do primeiro READ.\n"
            "4. Procure por MOVE de campo PIC X para campo PIC 9 sem conversão.\n\n"
            "**Prevenção:** use `PERFORM VARYING idx FROM 1 BY 1 UNTIL idx > MAX-OCCURS`."
        ),
    ),
    (
        "O job CONCIL01 abendou com SQLCODE -911. O que significa e como resolver?",
        "O job processa 500.000 faturas por execução.",
        (
            "SQLCODE -911 é Deadlock ou Lock Timeout no DB2.\n\n"
            "**Causa provável no CONCIL01:** o job lê FATURA e PAGAMENTO sem COMMIT "
            "intermediário, mantendo locks por toda a execução. Se outro job (FATURA01) "
            "rodar em paralelo e acessar as mesmas linhas, ocorre deadlock.\n\n"
            "**Solução:**\n"
            "1. Adicione `EXEC SQL COMMIT END-EXEC` a cada 1.000 registros processados.\n"
            "2. Execute FATURA01 e CONCIL01 em janelas batch separadas (não em paralelo).\n"
            "3. Revise a ordem de acesso: sempre acesse FATURA antes de PAGAMENTO.\n"
            "4. Configure `LOCK TIMEOUT 30` no BIND do plano LCCONPL.\n\n"
            "**Restart:** após resolver, reprocesse a partir do último ponto de COMMIT "
            "usando o GDG de controle."
        ),
    ),
    # ── JCL ───────────────────────────────────────────────────────────────────
    (
        "Como funciona o parâmetro COND no JCL e como usá-lo no ciclo LCDIA01?",
        "",
        (
            "O parâmetro COND no JCL controla a execução condicional de steps.\n\n"
            "`COND=(rc,op)` — o step é **pulado** se a condição for verdadeira:\n"
            "- `COND=(4,LT)` → pula se qualquer RC anterior < 4\n"
            "- `COND=(8,LE)` → pula se qualquer RC anterior ≤ 8\n\n"
            "**No LCDIA01:**\n"
            "```jcl\n"
            "//VALID  EXEC PGM=ARQVAL01\n"
            "//FATURA EXEC PGM=FATURA01,COND=(8,LE)\n"
            "```\n"
            "Se ARQVAL01 retornar RC=8 (erros no arquivo), o step FATURA01 é pulado, "
            "evitando faturamento com dados inválidos.\n\n"
            "**Convenção de RCs no LifeCore:**\n"
            "- 0: sucesso total\n- 4: avisos, continua\n- 8: erros, steps dependentes pulados\n"
            "- 12: erro grave, job cancelado\n- 16: abend crítico"
        ),
    ),
    (
        "O que é um GDG e como ele é usado no LifeCore-Mainframe?",
        "",
        (
            "GDG (Generation Data Group) é uma família de datasets sequenciais no z/OS "
            "onde cada execução gera uma nova geração (+1), mantendo histórico automático.\n\n"
            "**No LifeCore:**\n"
            "- `LIFECORE.DATA.APOLICE.G0001V00` = geração atual\n"
            "- `LIFECORE.DATA.APOLICE(0)` = geração corrente no JCL\n"
            "- `LIFECORE.DATA.APOLICE(-1)` = geração anterior\n"
            "- `LIFECORE.DATA.APOLICE(+1)` = próxima geração (criação)\n\n"
            "**Criação:** o job LCSETUP1 cria o índice GDG com IDCAMS DEFINE GDG.\n"
            "**Benefício:** permite restart automático — se o job falhar, a geração "
            "corrompida é descartada e a anterior ainda existe."
        ),
    ),
    # ── DB2 e SQL embutido ────────────────────────────────────────────────────
    (
        "Mostre como usar um cursor DB2 em COBOL para percorrer a tabela FATURA.",
        "COBOL GnuCOBOL com ocesql ou IBM COBOL com DB2 pre-compiler.",
        (
            "```cobol\n"
            "       WORKING-STORAGE SECTION.\n"
            "           EXEC SQL INCLUDE SQLCA   END-EXEC.\n"
            "           EXEC SQL INCLUDE DCLGEN_FATURA END-EXEC.\n"
            "           01 WS-FIM-CURSOR PIC X VALUE 'N'.\n\n"
            "       PROCEDURE DIVISION.\n"
            "           EXEC SQL\n"
            "               DECLARE CUR-FATURA CURSOR FOR\n"
            "               SELECT CD_FATURA, VL_PREMIO_BRUTO, CD_STATUS\n"
            "               FROM FATURA\n"
            "               WHERE CD_EMPRESA = :WS-CD-EMPRESA\n"
            "               AND CD_STATUS = 'PE'\n"
            "           END-EXEC.\n\n"
            "           EXEC SQL OPEN CUR-FATURA END-EXEC.\n"
            "           PERFORM UNTIL WS-FIM-CURSOR = 'S'\n"
            "               EXEC SQL\n"
            "                   FETCH CUR-FATURA\n"
            "                   INTO :CD-FATURA, :VL-PREMIO-BRUTO, :CD-STATUS\n"
            "               END-EXEC\n"
            "               IF SQLCODE = +100\n"
            "                   MOVE 'S' TO WS-FIM-CURSOR\n"
            "               ELSE IF SQLCODE < 0\n"
            "                   PERFORM 9000-TRATA-ERRO-SQL\n"
            "               ELSE\n"
            "                   PERFORM 2000-PROCESSA-FATURA\n"
            "               END-IF\n"
            "           END-PERFORM.\n"
            "           EXEC SQL CLOSE CUR-FATURA END-EXEC.\n"
            "```\n\n"
            "**Pontos críticos:** sempre feche o cursor. SQLCODE +100 = fim dos dados. "
            "Faça COMMIT a cada 1.000 registros para evitar -911."
        ),
    ),
    # ── Negócio (VGC/GLB) ────────────────────────────────────────────────────
    (
        "Quais são os cinco tipos de capital segurado suportados pelo CALCCAP?",
        "Produto: VGC (Vida em Grupo Coletivo).",
        (
            "O CALCCAP suporta cinco tipos de capital, controlados pelo campo "
            "TP-CAPITAL-SEG no CPYAPOL:\n\n"
            "**F — Fixo:** valor constante durante toda a vigência. "
            "Mais simples, usado em apólices de pequenas empresas.\n\n"
            "**E — Escalonado com IPCA:** o capital cresce com o IPCA ao longo do tempo. "
            "Fórmula: `CAPITAL = CAPITAL-BASE × (1 + IPCA/100) ^ ANOS`. "
            "O CALCCAP usa operador `**` do GnuCOBOL para a potenciação.\n\n"
            "**M — Múltiplo salarial:** `CAPITAL = SALARIO-BASE × FATOR-MULTIPLICADOR`. "
            "O FATOR-MULT é informado na proposta.\n\n"
            "**B — Por faixa etária/salarial:** cálculo progressivo por faixas, "
            "similar ao INSS. Cada faixa tem seu capital base.\n\n"
            "**P — Por cargo/plano:** diferente para cada cargo definido na tabela "
            "de parâmetros da empresa (PARAMETRO_ROTINA)."
        ),
    ),
    (
        "Como funciona o fluxo Proposta → Aceitação → Apólice no LifeCore?",
        "",
        (
            "1. **Proposta** é criada com status AN (Em Análise) via `POST /api/emissao/propostas`.\n\n"
            "2. **Aceitação automática** (tp_aceite=AU): se o segurado atende aos critérios "
            "de PARAMETRO_ROTINA (nr_dias_aceitacao_auto, cd_status_aceitacao), "
            "o sistema aceita sem intervenção humana.\n\n"
            "3. **Aceitação manual** (tp_aceite=MA): analista revisa e aceita/recusa via "
            "`POST /api/emissao/propostas/{nr}/aceitar`.\n\n"
            "4. Ao aceitar, o sistema gera automaticamente a **Apólice** com número "
            "no formato `{ano}.APO.{seq:06d}` e status AT (Ativa).\n\n"
            "5. No batch COBOL, o FATURA01 lê as apólices ativas do DB2 e gera "
            "a fatura mensal por estipulante."
        ),
    ),
    # ── PCI e Segurança ───────────────────────────────────────────────────────
    (
        "Como o LifeCore garante conformidade PCI-DSS no processamento de pagamentos?",
        "",
        (
            "O LifeCore segue as diretrizes PCI-DSS para pagamentos por cartão:\n\n"
            "**1. Nunca armazenar PAN completo:** o copybook CPYPAGT armazena apenas "
            "`NR-TOKEN-CARTAO` (token do adquirente) e `NR-ULTIMOS-4` (últimos 4 dígitos). "
            "O PAN completo nunca chega ao batch COBOL.\n\n"
            "**2. Mascaramento em logs:** o Output Guardrail da AI Layer detecta e "
            "mascara qualquer padrão de 16 dígitos antes de exibir ao usuário.\n\n"
            "**3. RACF no z/OS:** acesso aos datasets `LIFECORE.DATA.*` é restrito "
            "por perfil RACF — somente os jobs do ciclo batch têm permissão de UPDATE.\n\n"
            "**4. Trilha de auditoria:** toda ação é registrada em AUDITORIA_ACAO "
            "com usuário, timestamp, módulo e referência."
        ),
    ),
]


# ── Formatadores ──────────────────────────────────────────────────────────────


def to_alpaca(instruction: str, input_ctx: str, output: str) -> dict:
    return {
        "instruction": instruction,
        "input": input_ctx,
        "output": output,
    }


def to_sharegpt(instruction: str, input_ctx: str, output: str) -> dict:
    human = instruction if not input_ctx else f"{instruction}\n\nContexto: {input_ctx}"
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": human},
            {"from": "gpt", "value": output},
        ]
    }


def to_chatml(instruction: str, input_ctx: str, output: str) -> dict:
    human = instruction if not input_ctx else f"{instruction}\n\nContexto: {input_ctx}"
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": human},
            {"role": "assistant", "content": output},
        ]
    }


def build_dataset(fmt: Format = "chatml") -> list[dict]:
    """Constrói o dataset no formato especificado."""
    converters = {
        "alpaca": to_alpaca,
        "sharegpt": to_sharegpt,
        "chatml": to_chatml,
    }
    fn = converters[fmt]
    return [fn(instr, ctx, out) for instr, ctx, out in RAW_PAIRS]


def save_dataset(path: str, fmt: Format = "chatml") -> int:
    """Salva o dataset em JSONL. Retorna o número de exemplos."""
    items = build_dataset(fmt)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    logger.info("Dataset salvo: %s (%d exemplos, formato=%s)", path, len(items), fmt)
    return len(items)


def get_stats(dataset: list[dict] | None = None) -> dict:
    """Estatísticas do dataset para documentação."""
    if dataset is None:
        dataset = build_dataset("chatml")
    total = len(dataset)
    avg_output_len = sum(
        len(item["messages"][2]["content"].split()) for item in dataset
    ) / max(1, total)
    return {
        "total_examples": total,
        "format": "chatml",
        "avg_output_words": round(avg_output_len, 1),
        "system_prompt_chars": len(SYSTEM_PROMPT),
        "categories": {
            "abend": 3,
            "jcl": 2,
            "db2": 1,
            "negocio": 2,
            "seguranca": 1,
        },
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Gera dataset de fine-tuning do LifeCore."
    )
    parser.add_argument(
        "--format", choices=["alpaca", "sharegpt", "chatml"], default="chatml"
    )
    parser.add_argument("--output", default="lifecore_finetune.jsonl")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(get_stats(), indent=2, ensure_ascii=False))
    else:
        n = save_dataset(args.output, args.format)
        print(f"Dataset gerado: {args.output} ({n} exemplos)")
