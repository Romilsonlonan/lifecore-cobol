# LifeCore-Mainframe

> **Camada Legacy Core do LifeCore IQ** — Arquitetura mainframe z/OS com COBOL, JCL, DB2 e ciclo batch completo de seguros e pagamentos. Executável localmente com GnuCOBOL + PostgreSQL; validável no IBM Z Xplore com z/OS real.

---

## Visão da Arquitetura

```
                     LIFECORE IQ (Next.js / FastAPI)
                               │
                        INTEGRATION LAYER
                    (arquivos, eventos, REST API)
                               │
 ┌─────────────────────────────┴─────────────────────────────┐
 │                  LEGACY CORE (z/OS)                       │
 │                                                           │
 │  TSO/ISPF ── datasets (PDS / sequenciais / VSAM / GDG)    │
 │                                                           │
 │  JCL ──► Scheduler batch ──► Programas COBOL ──► DB2      │
 │                                                           │
 │  Segurança: RACF │ Logs: SYSOUT/SDSF │ Abends/Dumps       │
 └─────────────────────────────┬─────────────────────────────┘
                               │
                    Data Platform / Quality Intelligence
                    (catálogo de abends, RAG, runbooks)
```

---

## Estrutura do Repositório

```
LifeCore-Mainframe/
│
├── COPYLIB/          Layouts de arquivo (copybooks)
│   ├── CPYAPOL.cpy   Apólice e segurado (300 bytes)
│   ├── CPYFATU.cpy   Fatura por estipulante (250 bytes)
│   ├── CPYPAGT.cpy   Pagamento — token PCI, NSU, bandeira (200 bytes)
│   ├── CPYCONC.cpy   Resultado de conciliação (220 bytes)
│   └── CPYERRO.cpy   Registro de quarentena (180 bytes)
│
├── SRC/COBOL/        Fontes COBOL
│   ├── ARQVAL01.cbl  Validação do arquivo de apólices
│   ├── VGCCAP01.cbl  Cálculo de capital (F/E/M/B/P)
│   ├── FATURA01.cbl  Geração de faturamento por estipulante (DB2)
│   ├── PAGTO01.cbl   Baixa de pagamentos (DB2)
│   ├── CONCIL01.cbl  Conciliação fatura × pagamento (DB2)
│   ├── COMIS01.cbl   Cálculo de comissões
│   ├── CLEAR01.cbl   Leitura do arquivo de clearing da bandeira
│   ├── SETTLE01.cbl  Conciliação de liquidação × agenda de recebíveis
│   └── DISPUT01.cbl  Chargebacks e abertura de disputas (DB2)
│
├── JCL/
│   ├── LCSETUP1.jcl  Criação de GDGs e VSAM (executar 1× por ambiente)
│   └── LCDIA01.jcl   Ciclo batch diário completo (13 steps)
│
├── SQL/
│   └── schema.sql    DDL — SEGURADO, APOLICE, COBERTURA, FATURA,
│                           PAGAMENTO, CONCILIACAO, DISPUTA
│
├── RUNBOOK/
│   └── ABEND-CATALOG.md  S0C7, S0C4, S322, S806, -904/-911/-913
│
├── SCRIPTS/
│   ├── compile.sh    Compila todos os programas (GnuCOBOL / ocesql)
│   ├── run-cycle.sh  Executa o ciclo diário local
│   └── setup-db.sh   Cria banco PostgreSQL e aplica o schema
│
├── TESTDATA/
│   ├── APOLICE_OK.DAT      4 apólices válidas
│   ├── APOLICE_ERROS.DAT   4 registros com falhas propositais (E000xx)
│   ├── APOLICE_S0C7.DAT    Arquivo para provocar abend S0C7
│   ├── FATURA_OK.DAT       2 faturas geradas
│   └── PAGAMENTO_OK.DAT    2 pagamentos com token PCI-compliant
│
└── DATA/             Dados de execução (gerados em runtime)
    ├── INPUT/
    ├── OUTPUT/
    ├── QUARANTINE/
    └── GDG/
```

---

## Ciclo Batch Diário

```
RECEBE ARQUIVO
     │
SORT (CNPJ + Nº Apólice)
     │
ARQVAL01 ── erros → QUARENTENA (CPYERRO)
     │
VGCCAP01 (capital F/E/M/B/P)
     │
FATURA01 (agrupa por CNPJ → INSERT FATURA)
     │
SORT PAGAMENTOS (Nº Fatura)
     │
PAGTO01 (UPDATE FATURA, baixa pagamento)
     │
CONCIL01 (match fatura × pagto → INSERT CONCILIACAO)
     │
COMIS01 (5% sobre conciliado OK)
     │
CLEAR01 (arquivo de clearing da bandeira)
     │
SETTLE01 (clearing × agenda de recebíveis)
     │
DISPUT01 (chargebacks e divergências → INSERT DISPUTA)
     │
ICETOOL (COUNT de todos os arquivos do dia)
```

---

## Programas COBOL

| Programa | Função | SQL | RC máx. esperado |
|---|---|---|---|
| `ARQVAL01` | Validação de apólices + quarentena | Não | 8 (erros) |
| `VGCCAP01` | Cálculo de capital (5 tipos) | Não | 0 |
| `FATURA01` | Faturamento por estipulante | Sim | 8 |
| `PAGTO01`  | Baixa de pagamentos | Sim | 8 |
| `CONCIL01` | Conciliação fatura × pagamento | Sim | 4 (divergências) |
| `COMIS01`  | Cálculo de comissões | Não | 0 |
| `CLEAR01`  | Clearing da bandeira | Não | 0 |
| `SETTLE01` | Liquidação × agenda recebíveis | Não | 4 |
| `DISPUT01` | Chargebacks e disputas | Sim | 4 |

---

## Tipos de Capital Segurado (VGCCAP01)

| Código | Tipo | Cálculo |
|---|---|---|
| `F` | Fixo | Valor já definido no arquivo |
| `E` | Escalonado | Salário × fator (cresce com tempo) |
| `M` | Múltiplo Salarial | Salário × multiplicador |
| `B` | Por Faixa | Tabela de 5 faixas salariais |
| `P` | Paramétrico | Salário × fator × parcelas |

---

## Ecossistema de Pagamentos

```
Pagador → Estipulante/Corretora → Adquirente → Bandeira → Emissor
                AUTORIZAÇÃO  (ISO 8583: 0100/0110, estorno 0400)
                      │
                   CAPTURA
                      │
               COMPENSAÇÃO  ← CLEAR01 (arquivo de clearing)
                      │
                LIQUIDAÇÃO  ← SETTLE01 (agenda de recebíveis)
                      │
                CONCILIAÇÃO → DISPUT01 (chargeback/divergência)
```

**Regras PCI-DSS implementadas:**
- `CPYPAGT`: armazena apenas **token** e **últimos 4 dígitos** — nunca o PAN completo.
- Campos de token limitados a 32 chars sem qualquer informação sensível real.
- `DS_TOKEN_CARTAO` e `NR_CARTAO_ULTIMOS4` na tabela `PAGAMENTO`.

---

## Convenção de Return Code

| RC | Significado |
|---|---|
| 0 | Sucesso total |
| 4 | Avisos (divergências não críticas) |
| 8 | Erros de negócio (registros inválidos) |
| 12 | Erro crítico de I/O ou DB2 |
| 16 | Abend ou erro fatal |

---

## Códigos de Erro (CPYERRO)

| Código | Descrição |
|---|---|
| `E00001` | CPF do segurado ausente ou inválido |
| `E00002` | CNPJ do estipulante inválido |
| `E00003` | Capital segurado zero ou produto inválido |
| `E00004` | Vigência inválida ou ausente |
| `E00005` | Campo COMP-3 corrompido (provoca S0C7) |
| `E00006` | Apólice duplicada |
| `E00007` | Apólice não encontrada no DB2 |
| `E00008` | Fatura não encontrada |

---

## Como Executar Localmente

### 1. Instalar dependências

```bash
# Fedora / RHEL
sudo dnf install gnucobol postgresql

# Debian / Ubuntu
sudo apt install gnucobol postgresql

# ocesql (DB2 emulado via PostgreSQL)
# https://github.com/opensourcecobol/Open-COBOL-ESQL
```

### 2. Criar banco e schema

```bash
./SCRIPTS/setup-db.sh create
```

### 3. Compilar os programas

```bash
./SCRIPTS/compile.sh all
# ou individual:
./SCRIPTS/compile.sh ARQVAL01
```

### 4. Executar o ciclo

```bash
# Ciclo normal com dados OK
./SCRIPTS/run-cycle.sh

# Ciclo com erros de negócio propositais
./SCRIPTS/run-cycle.sh erros

# Provoca S0C7 (COMP-3 corrompido)
./SCRIPTS/run-cycle.sh s0c7
```

---

## IBM Z Xplore (z/OS Real)

Para executar em ambiente z/OS real:

1. Suba os fontes via Zowe CLI:
   ```bash
   zowe files ul ftds "LIFECORE.SRC.COBOL(ARQVAL01)" SRC/COBOL/ARQVAL01.cbl
   ```
2. Compile com IGYCRCTL (compilador IBM COBOL) e link-edite para `LIFECORE.LOAD`.
3. Faça BIND dos planos DB2 (`LCFATPL`, `LCCONPL`, etc.).
4. Ajuste HLQ, subsistema DB2 e loadlib em `LCDIA01.jcl`.
5. Submeta `LCSETUP1.jcl` uma vez, depois `LCDIA01.jcl` diariamente.

> **Diferença local × z/OS:** GnuCOBOL usa paths Unix para arquivos; z/OS usa DDnames no JCL. Os programas estão preparados para ambos via variáveis de ambiente (local) ou DDs (z/OS).

---

## Regulatório

| Área | Norma | Implementação |
|---|---|---|
| Segurança de dados de cartão | PCI-DSS | Token + últimos 4 dígitos apenas |
| Proteção de dados pessoais | LGPD | CPF/nome não logados em texto claro |
| Seguros | SUSEP | Campos de produto VGC/GLB validados |
| Pagamentos | Banco Central | Fluxo de autorização/liquidação documentado |

> Conformidade formal requer validação jurídica. Este projeto é referência técnica de implementação.

---

## Catálogo de Abends

Veja [`RUNBOOK/ABEND-CATALOG.md`](RUNBOOK/ABEND-CATALOG.md) para diagnóstico detalhado de:
S0C7 · S0C4 · S322 · S806 · SQLCODE -904/-911/-913

---

## Roadmap

- [x] Copybooks e layouts de arquivo
- [x] ARQVAL01 + ciclo JCL
- [x] Ciclo batch de faturamento com DB2
- [x] Conciliação de pagamentos
- [x] Catálogo de abends e runbooks
- [x] Clearing, liquidação e disputas de cartão
- [ ] DCLGEN automático a partir do schema PostgreSQL
- [ ] CI/CD com GitHub Actions (compile + run-cycle)
- [ ] RAG sobre o catálogo de abends (Quality Intelligence)
- [ ] Integração com a Integration Layer do LifeCore IQ
