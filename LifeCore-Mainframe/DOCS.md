# LifeCore-Mainframe — Documentação Técnica Completa

> **Versão**: 2.0.0 | **Stack**: COBOL · JCL · DB2 · FastAPI · Python 3.12 · OpenTelemetry · Playwright · ChromaDB

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Estrutura de Diretórios](#3-estrutura-de-diretórios)
4. [Legacy Core — COBOL / z/OS](#4-legacy-core--cobol--zos)
   - [Copybooks](#41-copybooks)
   - [Programas COBOL](#42-programas-cobol)
   - [JCL — Ciclo Batch](#43-jcl--ciclo-batch)
   - [Ciclo de Pagamentos (PCI)](#44-ciclo-de-pagamentos-pci)
5. [Banco de Dados (SQL)](#5-banco-de-dados-sql)
6. [Integration Layer — FastAPI](#6-integration-layer--fastapi)
   - [Variáveis de Ambiente](#61-variáveis-de-ambiente)
   - [Endpoints por Módulo](#62-endpoints-por-módulo)
   - [Schemas Pydantic](#63-schemas-pydantic)
   - [Serviços Internos](#64-serviços-internos)
7. [AI Layer](#7-ai-layer)
   - [RAG Engine](#71-rag-engine)
   - [Agente COBOL (Tool Calling)](#72-agente-cobol-tool-calling)
   - [MCP Server](#73-mcp-server)
   - [Guardrails e AI Security](#74-guardrails-e-ai-security)
   - [LLM Evaluation](#75-llm-evaluation)
   - [Dataset de Fine-tuning](#76-dataset-de-fine-tuning)
8. [Observabilidade — OpenTelemetry](#8-observabilidade--opentelemetry)
9. [Testes](#9-testes)
10. [CI/CD](#10-cicd)
11. [Scripts](#11-scripts)
12. [Dependências](#12-dependências)
13. [Como Executar](#13-como-executar)
14. [Convenções e Padrões](#14-convenções-e-padrões)

---

## 1. Visão Geral

O **LifeCore-Mainframe** é a camada Legacy Core do sistema **LifeCore IQ**, que modela um ambiente mainframe IBM z/OS real para seguros de vida em grupo (**VGC** — Vida em Grupo Coletivo e **GLB** — Grupo de Vida em Grupo com participação de lucro).

O projeto tem três objetivos simultâneos:

| Objetivo | Descrição |
|---|---|
| **Educacional** | Demonstrar arquitetura z/OS real: COBOL, JCL, DB2, GDG, VSAM, RACF |
| **Funcional** | Processar apólices, faturamento, pagamentos, conciliação e sinistros |
| **Moderno** | Expor o legado via API REST (FastAPI) + AI Layer (RAG, Agentes, MCP) |

---

## 2. Arquitetura

```
                ┌──────────────────────────────────────┐
                │        FRONT-END (Next.js)            │
                │   Painel · Emissão · Sinistro · etc.  │
                └──────────────┬───────────────────────┘
                               │ HTTPS REST
                ┌──────────────▼───────────────────────┐
                │    INTEGRATION LAYER (FastAPI)        │
                │         roda em Linux/Cloud           │
                │                                       │
                │  /api/cadastros  /api/emissao          │
                │  /api/sinistro   /api/cosseguro        │
                │  /api/impressao  /api/pessoas          │
                │  /api/painel     /api/ai               │
                │                                       │
                │  OpenTelemetry → X-Trace-Id           │
                │  Middleware de correlação              │
                └──────┬──────────────────┬────────────┘
                       │                  │
           subprocess  │              Zowe CLI
           (local dev) │          (z/OS IBM Z Xplore)
                       │                  │
         ┌─────────────▼──────────────────▼──────────────┐
         │              LEGACY CORE (z/OS)                │
         │                                                │
         │  TSO/ISPF · RACF · SDSF · Dumps               │
         │                                                │
         │  JCL LCDIA01 ──► Scheduler                    │
         │    STEP010 ARQVAL01  (valida arquivo)          │
         │    STEP020 VGCCAP01  (calcula capital)         │
         │    STEP030 FATURA01  (gera faturamento)        │
         │    STEP040 PAGTO01   (baixa pagamentos)        │
         │    STEP050 CONCIL01  (conciliação)             │
         │    STEP060 COMIS01   (comissões)               │
         │    STEP070 CLEAR01   (clearing bandeira)       │
         │    STEP080 SETTLE01  (liquidação)              │
         │    STEP090 DISPUT01  (disputas/chargeback)     │
         │                │                               │
         │           EXEC SQL                            │
         │                │                               │
         │        DB2 / PostgreSQL                        │
         │  (APOLICE, SEGURADO, FATURA, PAGAMENTO…)       │
         └────────────────────────────────────────────────┘
                               │
         ┌─────────────────────▼──────────────────────────┐
         │                  AI LAYER                       │
         │                                                 │
         │  RAG Engine      → ChromaDB + MiniLM-L6-v2     │
         │  Agente COBOL    → Tool Calling (ReAct loop)   │
         │  MCP Server      → Claude Desktop / Cursor     │
         │  Guardrails      → Input/Action/Output         │
         │  LLM Evaluation  → LLM-as-a-Judge + Rule-based │
         │  Fine-tuning     → Dataset ChatML/Alpaca       │
         └─────────────────────────────────────────────────┘
```

---

## 3. Estrutura de Diretórios

```
LifeCore-Mainframe/
├── COPYLIB/                    ← Layouts de arquivo (copybooks COBOL)
│   ├── CPYAPOL.cpy             ← Apólice + Segurado         (300 bytes)
│   ├── CPYFATU.cpy             ← Fatura por Estipulante     (250 bytes)
│   ├── CPYPAGT.cpy             ← Pagamento PCI-compliant    (200 bytes)
│   ├── CPYCONC.cpy             ← Resultado de Conciliação   (220 bytes)
│   ├── CPYERRO.cpy             ← Registro de Quarentena     (180 bytes)
│   ├── CPYSQLCA.cpy            ← SQL Communication Area     (compartilhado)
│   ├── CPYCLR.cpy              ← Clearing bandeira          (compartilhado)
│   └── CPYLIQ.cpy              ← Liquidação agenda recebíveis
│
├── SRC/COBOL/                  ← Fontes COBOL (formato fixo, col 7-72)
│   ├── ARQVAL01.cbl            ← Validação arquivo entrada → quarentena
│   ├── VGCCAP01.cbl            ← Orquestrador cálculo de capital
│   ├── CALCCAP.cbl             ← Subprograma: 5 tipos de capital (compile -m)
│   ├── FATURA01.cbl            ← Geração faturamento por estipulante
│   ├── PAGTO01.cbl             ← Baixa de pagamentos
│   ├── CONCIL01.cbl            ← Conciliação fatura × pagamento
│   ├── COMIS01.cbl             ← Cálculo de comissões
│   ├── CLEAR01.cbl             ← Leitura arquivo clearing bandeira
│   ├── SETTLE01.cbl            ← Liquidação × agenda de recebíveis
│   └── DISPUT01.cbl            ← Chargebacks e disputas
│
├── JCL/                        ← Jobs JCL
│   ├── LCSETUP1.jcl            ← Criação GDGs e VSAM (executar 1 vez)
│   ├── LCDIA01.jcl             ← Ciclo diário completo (13 steps)
│   └── LCIMP01.jcl             ← Job de importação (acionado via Zowe)
│
├── SQL/
│   ├── schema.sql              ← Schema v1 (referência legada)
│   └── schema_v2.sql           ← Schema v2 — 23 tabelas + seeds + índices
│
├── TESTDATA/                   ← Arquivos de teste em formato fixo
│   ├── APOLICE_OK.DAT          ← 3 apólices válidas
│   ├── APOLICE_ERROS.DAT       ← Erros intencionais (CPF inválido, duplicado)
│   ├── APOLICE_S0C7.DAT        ← COMP-3 corrompido → provoca abend S0C7
│   ├── FATURA_OK.DAT           ← Faturas de teste
│   └── PAGAMENTO_OK.DAT        ← Pagamentos de teste
│
├── RUNBOOK/
│   └── ABEND-CATALOG.md        ← S0C7, S0C4, S322, S806, -904, -911, -913
│
├── SCRIPTS/
│   ├── compile.sh              ← Compila todos os programas COBOL
│   ├── run-cycle.sh            ← Simula ciclo batch localmente
│   └── setup-db.sh             ← Cria banco PostgreSQL com schema_v2.sql
│
├── LOAD/                       ← Binários compilados (git ignored)
│   ├── ARQVAL01, FATURA01…     ← Executáveis (cobc -x)
│   └── CALCCAP.so              ← Módulo compartilhado (cobc -m)
│
├── .github/workflows/
│   └── ci.yml                  ← 8 jobs: compile · lint · integration · schema
│                                          · api-test · e2e · security · summary
│
└── integration-layer/          ← FastAPI (Python 3.12)
    ├── app/
    │   ├── main.py             ← App FastAPI v2.0.0 (15 routers registrados)
    │   ├── api/
    │   │   ├── importacao.py   ← POST /api/apolices/importar
    │   │   ├── jobs.py         ← GET  /api/jobs/{id}/status
    │   │   ├── resultados.py   ← GET  /api/apolices/resultado/{id}
    │   │   ├── cadastros/
    │   │   │   ├── empresa.py  ← CRUD /api/cadastros/empresas
    │   │   │   ├── congenere.py← CRUD /api/cadastros/congeneres
    │   │   │   └── segurado.py ← CRUD /api/cadastros/segurados
    │   │   ├── emissao/
    │   │   │   ├── proposta.py ← POST/GET/aceitar/recusar propostas
    │   │   │   └── apolice.py  ← GET/cancelar apólices
    │   │   ├── sinistro/
    │   │   │   ├── sinistro.py ← CRUD + analisar/pagar/encerrar
    │   │   │   └── kit_ecm.py  ← Documentos digitais vinculados
    │   │   ├── impressao/
    │   │   │   └── controle.py ← Controle geração documentos
    │   │   ├── cosseguro/
    │   │   │   └── cosseguro.py← Participação entre seguradoras
    │   │   ├── pessoas/
    │   │   │   └── pessoas.py  ← Corretores, beneficiários, etc.
    │   │   ├── painel.py       ← GET /api/painel (KPIs + pipeline)
    │   │   └── ai_router.py    ← /api/ai/* (RAG, agente, evals…)
    │   ├── ai/
    │   │   ├── rag/engine.py   ← Embedder + VectorStore + Indexer + RAGEngine
    │   │   ├── agents/
    │   │   │   ├── tools.py    ← 6 tools com JSON Schema + catálogo abends
    │   │   │   └── agent.py    ← Loop ReAct + streaming
    │   │   ├── mcp/server.py   ← MCP Server (tools + resources + prompts)
    │   │   ├── guardrails/
    │   │   │   └── pipeline.py ← Input + Action + Output + RateLimiter
    │   │   ├── evals/
    │   │   │   └── evaluator.py← RuleBasedEvaluator + LLMJudge + dataset
    │   │   └── finetune/
    │   │       └── dataset.py  ← 9 pares Q/A em ChatML/Alpaca/ShareGPT
    │   ├── core/
    │   │   ├── config.py       ← Settings (pydantic-settings)
    │   │   └── telemetry.py    ← OpenTelemetry setup + middleware
    │   ├── schemas/
    │   │   ├── apolice.py      ← Schemas importação/jobs (v1)
    │   │   └── lifecore.py     ← Schemas completos todos os módulos (v2)
    │   └── services/
    │       ├── conversor.py    ← CSV/XLSX/JSON → fixed-width (300 bytes)
    │       └── batch_connector.py ← stub / local / Zowe dispatcher
    ├── tests/
    │   ├── test_api.py         ← 39 testes API (módulos negócio)
    │   ├── test_ai_layer.py    ← 33 testes AI Layer
    │   └── e2e/
    │       ├── conftest.py     ← Sobe uvicorn antes da suite E2E
    │       └── test_swagger_smoke.py ← 8 testes Playwright (browser)
    ├── requirements.txt
    └── .env.example
```

---

## 4. Legacy Core — COBOL / z/OS

### 4.1 Copybooks

Todos os layouts são de largura fixa. Campos monetários usam `COMP-3` (packed-decimal). A tabela abaixo lista cada copybook, seu tamanho e campos principais.

| Copybook | Bytes | Campos principais |
|---|---|---|
| **CPYAPOL** | 300 | `APO-NUMERO`, `APO-PRODUTO` (VGC/GLB), `APO-TIPO-CAPITAL` (F/E/M/B/P), `APO-CAPITAL-SEGURADO COMP-3`, `APO-PREMIO-BRUTO COMP-3` |
| **CPYFATU** | 250 | `FAT-NUMERO`, `FAT-ESTIPULANTE-CNPJ`, `FAT-COMPETENCIA`, `FAT-VALOR-BRUTO COMP-3`, `FAT-VALOR-LIQUIDO COMP-3`, `FAT-STATUS` (PE/PG/PP/AT/CA) |
| **CPYPAGT** | 200 | `PAG-TOKEN-CARTAO` (32), `PAG-CARTAO-ULTIMOS-4` — **PAN nunca armazenado** (PCI). `PAG-NSU`, `PAG-COD-AUTORIZACAO`, `PAG-BANDEIRA` (VISA/MCRD/ELOC) |
| **CPYCONC** | 220 | `CON-FATURA-NUMERO`, `CON-VALOR-FATURADO COMP-3`, `CON-VALOR-PAGO COMP-3`, `CON-STATUS` (OK/DV/SP/SF/DU) |
| **CPYERRO** | 180 | `ERR-APOLICE-NUMERO`, `ERR-CODIGO` (E00001–E00006), `ERR-DESCRICAO` |
| **CPYSQLCA** | — | SQL Communication Area compartilhada. `SQLCODE`, `SQLERRM`, `SQLSTATE` |
| **CPYCLR** | — | `CLR-NSU`, `CLR-BANDEIRA`, `CLR-VALOR COMP-3`, `CLR-DATA-CLEARING` |
| **CPYLIQ** | — | `LIQ-NSU`, `LIQ-VALOR-LIQUIDO COMP-3`, `LIQ-DATA-CREDITO`, `LIQ-STATUS` |

**Condition-names (nível 88) em CPYAPOL:**

| Campo-pai | Nível 88 | Valor |
|---|---|---|
| `APO-PRODUTO` | `APO-PRODUTO-VGC` | `'VGC'` |
| `APO-PRODUTO` | `APO-PRODUTO-GLB` | `'GLB'` |
| `APO-TIPO-CAPITAL` | `APO-CAP-FIXO` | `'F'` |
| `APO-TIPO-CAPITAL` | `APO-CAP-ESCALONADO` | `'E'` |
| `APO-TIPO-CAPITAL` | `APO-CAP-MULT-SALARIAL` | `'M'` |
| `APO-TIPO-CAPITAL` | `APO-CAP-POR-FAIXA` | `'B'` |
| `APO-TIPO-CAPITAL` | `APO-CAP-PARAMETRICO` | `'P'` |
| `APO-STATUS` | `APO-ATIVO` | `'AT'` |
| `APO-STATUS` | `APO-CANCELADO` | `'CA'` |

---

### 4.2 Programas COBOL

| Programa | Tipo | Função | Copybooks | Chama / É chamado |
|---|---|---|---|---|
| **ARQVAL01** | Executável | Valida arquivo entrada → quarentena | CPYAPOL, CPYERRO | — |
| **VGCCAP01** | Executável | Orquestra cálculo de capital | CPYAPOL, CPYSQLCA | `CALL 'CALCCAP'` |
| **CALCCAP** | Módulo (`.so`) | 5 tipos de capital (F/E/M/B/P) com IPCA | CPYAPOL | chamado por VGCCAP01 |
| **FATURA01** | Executável | Gera faturamento por estipulante | CPYAPOL, CPYFATU, CPYSQLCA | — |
| **PAGTO01** | Executável | Baixa pagamentos | CPYPAGT, CPYFATU, CPYSQLCA | — |
| **CONCIL01** | Executável | Concilia fatura × pagamento | CPYCONC, CPYFATU, CPYPAGT, CPYSQLCA | — |
| **COMIS01** | Executável | Calcula comissões do corretor | CPYFATU, CPYSQLCA | — |
| **CLEAR01** | Executável | Lê arquivo clearing da bandeira | CPYCLR, CPYSQLCA | — |
| **SETTLE01** | Executável | Liquida clearing × agenda recebíveis | CPYCLR, CPYLIQ, CPYSQLCA | — |
| **DISPUT01** | Executável | Trata chargebacks e abre disputas | CPYPAGT, CPYLIQ, CPYSQLCA | — |

**Compilação:**
```bash
# Executáveis
cobc -x -I COPYLIB -o LOAD/ARQVAL01 SRC/COBOL/ARQVAL01.cbl

# Módulo (subprograma — CALL)
cobc -m -I COPYLIB -o LOAD/CALCCAP  SRC/COBOL/CALCCAP.cbl
```

**Tipos de capital no CALCCAP:**

| Código | Nome | Fórmula |
|---|---|---|
| `F` | Fixo | `CAPITAL = APO-CAPITAL-SEGURADO` |
| `E` | Escalonado IPCA | `CAPITAL = BASE × (1 + IPCA/100) ^ ANOS` |
| `M` | Múltiplo salarial | `CAPITAL = APO-SALARIO-BASE × APO-FATOR-MULT` |
| `B` | Por faixa | Cálculo progressivo por faixas (estilo INSS) |
| `P` | Por cargo/plano | Lido de `PARAMETRO_ROTINA` no DB2 |

**Convenção de Return Codes:**

| RC | Significado |
|---|---|
| 0 | Sucesso total |
| 4 | Avisos — step seguinte continua |
| 8 | Erros — steps dependentes pulados (COND) |
| 12 | Erro grave — job cancelado |
| 16 | Abend crítico |

**Códigos de erro do ARQVAL01:**

| Código | Causa |
|---|---|
| E00001 | CPF inválido (dígito verificador) |
| E00002 | CNPJ estipulante inválido |
| E00003 | Produto desconhecido (não VGC/GLB) |
| E00004 | Tipo de capital inválido (não F/E/M/B/P) |
| E00005 | Capital segurado zerado |
| E00006 | Apólice duplicada no arquivo |

---

### 4.3 JCL — Ciclo Batch

**LCSETUP1.jcl** — execução única, cria:
- GDGs: `LIFECORE.DATA.APOLICE`, `LIFECORE.DATA.FATURA`, `LIFECORE.DATA.PAGAMENTO`
- VSAM KSDS: `LIFECORE.VSAM.PARAMETROS`

**LCDIA01.jcl** — ciclo diário (13 steps):

```
STEP010 IEFBR14    → Limpeza datasets temporários
STEP020 SORT       → Ordena apólices por CNPJ estipulante
STEP030 ARQVAL01   → Valida → OUTPUT / QUARANTINE
STEP040 SORT       → Ordena erros de quarentena
STEP050 FATURA01   → Gera fatura (DB2 via IKJEFT01)
STEP060 CONCIL01   → Concilia fatura × pagamento (DB2)
STEP070 SORT       → Ordena pagamentos por data
STEP080 PAGTO01    → Baixa pagamentos
STEP090 COMIS01    → Calcula comissões
STEP100 CLEAR01    → Lê clearing bandeira
STEP110 SETTLE01   → Liquidação
STEP120 DISPUT01   → Chargebacks
STEP130 ICETOOL    → Relatório resumo (contagens)
```

Encadeamento com `COND=(8,LE)` — se ARQVAL01 retornar RC≥8, steps 050–130 são pulados.

**LCIMP01.jcl** — importação acionada pela API (via Zowe CLI):
- Recebe arquivo convertido pela Integration Layer
- Executa apenas ARQVAL01 + VGCCAP01

---

### 4.4 Ciclo de Pagamentos (PCI)

```
Pagador ──► Estipulante ──► Adquirente ──► Bandeira ──► Emissor
                AUTORIZAÇÃO  (ISO 8583: 0100/0110)
                      │
                   CAPTURA  (confirma cobrança)
                      │
               COMPENSAÇÃO  (CLEAR01 — arquivo clearing)
                      │
                LIQUIDAÇÃO  (SETTLE01 — agenda recebíveis)
                      │
               CONCILIAÇÃO  (CONCIL01)
                      │
                 DISPUTAS   (DISPUT01 — chargeback)
```

**Regras PCI-DSS implementadas:**
- `CPYPAGT`: armazena apenas `PAG-TOKEN-CARTAO` (32 chars) + `PAG-CARTAO-ULTIMOS-4` — PAN completo nunca gravado
- Output Guardrail da AI Layer detecta e mascara padrões de 16 dígitos antes de exibir
- RACF (z/OS): datasets `LIFECORE.DATA.*` só acessíveis pelos jobs do ciclo batch

---

## 5. Banco de Dados (SQL)

**Schema v2** (`SQL/schema_v2.sql`) — 23 tabelas:

| Tabela | Descrição |
|---|---|
| `EMPRESA` | Seguradoras, estipulantes, corretoras, congêneres |
| `FILIAL` | Filiais da empresa |
| `CONGENERE` | Resseguradores e co-seguradoras |
| `SEGURADO` | Pessoa física segurada |
| `GRUPO_USUARIO` | Perfis de acesso (seed: SYSADM, OPERADOR, CONSULTA) |
| `PROPOSTA` | Proposta de seguro (status: AN/AA/PD/AC/RC/CA) |
| `APOLICE` | Apólice emitida (status: AT/CA/SU/EX) |
| `COBERTURA` | Coberturas da apólice (morte, invalidez, DIT…) |
| `MATRICULA_SEQ` | Sequência de matrícula por empresa |
| `SINISTRO` | Sinistro (status: AB/AN/PG/EN/RC) |
| `KIT_SINISTRO` | Documentos exigidos por tipo de evento |
| `FATURA` | Fatura mensal por estipulante |
| `PAGAMENTO` | Pagamento de fatura (token PCI, NSU, bandeira) |
| `CONCILIACAO` | Resultado conciliação fatura × pagamento |
| `DISPUTA` | Chargeback e divergências |
| `PARAMETRO_ROTINA` | Regras de aceitação automática por empresa |
| `PARAMETRO_INTERFACE` | Parâmetros de interface por código (seed) |
| `GRUPO_DOC_ECM` | Grupos de documentos ECM (seed: SIN, APO, COB) |
| `DOC_ECM` | Documentos digitais anexados |
| `CONTROLE_IMPRESSAO` | Controle de geração de documentos por módulo |
| `PERMISSAO_FECHAMENTO` | Permissões por data e módulo |
| `AUDITORIA_ACAO` | Trilha de auditoria de todas as ações |

---

## 6. Integration Layer — FastAPI

### 6.1 Variáveis de Ambiente

Todas definidas em `.env` (ver `.env.example`). Carregadas via `pydantic-settings`.

| Variável | Padrão | Descrição |
|---|---|---|
| `DATA_INPUT_DIR` | `/tmp/lifecore/DATA/INPUT` | Datasets de entrada |
| `DATA_OUTPUT_DIR` | `/tmp/lifecore/DATA/OUTPUT` | Saída do batch |
| `DATA_QUARANTINE_DIR` | `/tmp/lifecore/DATA/QUARANTINE` | Registros inválidos |
| `LOAD_DIR` | `/tmp/lifecore/LOAD` | Binários COBOL compilados |
| `DATABASE_URL` | `postgresql://postgres:lifecore@localhost:5432/lifecore` | PostgreSQL |
| `DB2_DSN` | — | String DRDA para a conexão da API ao DB2 z/OS; obrigatória para cadastros EMPRESA |
| `DB2_SCHEMA` | `LIFECORE` | Schema DB2 da tabela EMPRESA compartilhada com CICS |
| `BATCH_CONNECTOR` | `stub` | `stub` / `local` / `zowe`; controla batch, não a conexão DB2 da API |
| `ZOWE_PROFILE` | `zos-dev` | Perfil Zowe CLI |
| `ZOS_HLQ` | `LIFECORE` | High-Level Qualifier no z/OS |
| `ZOS_DB2_SYSTEM` | `DB2P` | Subsistema DB2 |
| `OTEL_ENABLED` | `false` | Ativa OpenTelemetry |
| `OTEL_SERVICE_NAME` | `lifecore-integration-layer` | Nome do serviço no trace |
| `OTEL_EXPORTER_TYPE` | `console` | `console` / `grpc` / `http` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Collector gRPC |
| `OTEL_EXPORTER_OTLP_HTTP_ENDPOINT` | `http://localhost:4318/v1/traces` | Collector HTTP |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `RAG_EMBED_MODEL` | `all-MiniLM-L6-v2` | Modelo de embeddings |
| `RAG_CHROMA_PATH` | `/tmp/lifecore_chroma` | Persistência ChromaDB |
| `RAG_COLLECTION` | `lifecore_docs` | Nome da coleção |
| `RAG_CHUNK_SIZE` | `500` | Palavras por chunk |
| `RAG_CHUNK_OVERLAP` | `80` | Overlap entre chunks |
| `RAG_TOP_K` | `5` | Chunks retornados por busca |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Endpoint LLM (Ollama) |
| `LLM_API_KEY` | `ollama` | Chave API (qualquer string para Ollama) |
| `LLM_MODEL` | `llama3.2` | Modelo LLM para geração |
| `LLM_JUDGE_MODEL` | `llama3.2` | Modelo para LLM-as-a-Judge |
| `AGENT_MAX_TURNS` | `8` | Limite de turnos do agente ReAct |
| `PROJECT_ROOT` | _(calculado)_ | Raiz do projeto para localizar COPYLIB/LOAD |

---

### 6.1.1 Cadastros compartilhados via DB2 z/OS

`EMPRESA` é a fonte única para o cadastro de estipulantes. A API usa o driver
IBM `ibm_db` e o valor `DB2_DSN`; o programa CICS `LCES` (`LCCICS04`) usa
SQL embutido na mesma tabela `LIFECORE.EMPRESA`. Não há fallback para memória
ou PostgreSQL: sem DB2 configurado a API retorna HTTP 503.

Antes de habilitar os fluxos:

1. Aplicar `SQL/DB2/001_EMPRESA.sql` uma única vez no schema DB2 `LIFECORE`.
2. Configurar `DB2_DSN` como string DRDA fornecida pelo administrador do DB2.
3. Gerar o mapa `LCMAPA04` e o copybook `LCMSET4` com `LCBMSC01`.
4. Compilar o programa e DBRM com `LCESBLC1`; vincular o DBRM ao package/plan
   permitido pela região CICS e habilitar os recursos CICS de `LCCSDUP1`.
5. Testar os dois fluxos contra a mesma instância e tabela DB2.

O cadastro compartilhado não significa que o processamento COBOL batch já
esteja sendo acionado por cada gravação web. Importações, cancelamentos e
emissão/impressão de faturas precisam de seus contratos e rotinas COBOL
específicos; a API não os simula nem os substitui.

#### Importação inicial para revisão

O portal também recebe planilhas CSV, XLSX, XLS e ODS ou um link público do
Google Sheets (compartilhado como “qualquer pessoa com o link — leitor”).
O usuário confere e ajusta o mapeamento de Sub, Módulo, Nome, Nascimento,
CPF e Admissão; salário, cargo e capital são excluídos. Esta etapa apenas
valida estrutura, formato de data, CPF com 11 dígitos e duplicidades dentro
do arquivo: não confirma elegibilidade nem cria cobertura/apólice.

1. Aplicar `SQL/DB2/002_IMPORTACAO_INICIAL.sql` no schema compartilhado antes
   de habilitar a gravação.
2. Configurar `DB2_DSN` e validar conectividade da API ao DB2.
3. Compilar o mapa/programa CICS com `JCL/LCBMSC01.jcl` e
   `JCL/LCIMP09.jcl`; instalar o programa, mapset e transação `LCIM` conforme
   `JCL/LCCSDUP1.csd`. A consulta CICS lê as mesmas tabelas DB2 da API.
4. Na interface, analisar, mapear, validar e então salvar. A validação não
   grava; o lote salvo recebe status `RV` (revisão), e linhas com crítica
   recebem `ER`. O vínculo ao estipulante/apólice e a liberação das vidas são
   etapas posteriores, ainda não automatizadas por este fluxo.

| Método | Path | Descrição |
|---|---|---|
| `POST` | `/api/cadastros/importacoes-iniciais/analisar` | Lê cabeçalhos e sugere mapeamento; não grava |
| `POST` | `/api/cadastros/importacoes-iniciais/validar` | Valida o mapeamento/conteúdo; não grava |
| `POST` | `/api/cadastros/importacoes-iniciais` | Persiste lote e linhas de revisão no DB2 |
| `GET` | `/api/cadastros/importacoes-iniciais?limite=20` | Lista lotes no DB2 |
| `GET` | `/api/cadastros/importacoes-iniciais/{id_importacao}` | Consulta lote e linhas no DB2 |

Todos os endpoints exigem perfil administrador. O arquivo/link pode ter até
10 MB e cada lote até 50.000 linhas. O CPF é mascarado nas prévias. O ID do
lote pode ser informado na transação CICS `LCIM` (opção 7 do menu após a
implantação).

Os scripts CICS/JCL/DDL são artefatos preparados, não uma implantação
comprovada: DB2 z/OS e CICS precisam compilar, instalar e validar esses recursos
no ambiente IBM antes do uso produtivo.

---

### 6.2 Endpoints por Módulo

#### Health
| Método | Path | Descrição |
|---|---|---|
| `GET` | `/health` | Status do serviço + versão |

#### Importação / Batch (Legado)
| Método | Path | Descrição |
|---|---|---|
| `POST` | `/api/apolices/importar` | Recebe CSV/XLSX/JSON → converte → dispara batch |
| `GET` | `/api/jobs/{id}/status` | Status de um job batch |
| `GET` | `/api/apolices/resultado/{id}` | Resultado do job (RC, log) |

#### Cadastros
| Método | Path | Descrição |
|---|---|---|
| `GET/POST` | `/api/cadastros/empresas` | Lista / cadastra empresa |
| `GET/PUT` | `/api/cadastros/empresas/{id}` | Detalha / altera status |
| `POST` | `/api/cadastros/importacoes-iniciais/analisar` | Analisa planilha de cadastro inicial |
| `POST` | `/api/cadastros/importacoes-iniciais/validar` | Valida mapeamento sem gravar |
| `POST/GET` | `/api/cadastros/importacoes-iniciais` | Grava lote de revisão / lista lotes |
| `GET` | `/api/cadastros/importacoes-iniciais/{id_importacao}` | Consulta lote e linhas |
| `GET/POST` | `/api/cadastros/congeneres` | Resseguradores |
| `DELETE` | `/api/cadastros/congeneres/{id}` | Remove congênere |
| `GET/POST` | `/api/cadastros/segurados` | Segurados / PF |
| `GET/PUT` | `/api/cadastros/segurados/{cpf}` | Detalha / atualiza |

#### Emissão
| Método | Path | Descrição |
|---|---|---|
| `POST/GET` | `/api/emissao/propostas` | Cria / lista propostas |
| `GET` | `/api/emissao/propostas/{nr}` | Detalha proposta |
| `POST` | `/api/emissao/propostas/{nr}/aceitar` | Aceita → gera apólice |
| `POST` | `/api/emissao/propostas/{nr}/recusar` | Recusa proposta |
| `GET` | `/api/emissao/apolices` | Lista apólices |
| `GET` | `/api/emissao/apolices/{nr}` | Detalha apólice |
| `PUT` | `/api/emissao/apolices/{nr}/cancelar` | Cancela apólice |

#### Sinistro
| Método | Path | Descrição |
|---|---|---|
| `POST/GET` | `/api/sinistro` | Abre / lista sinistros |
| `GET` | `/api/sinistro/{nr}` | Detalha sinistro |
| `PUT` | `/api/sinistro/{nr}/analisar` | Registra parecer |
| `PUT` | `/api/sinistro/{nr}/pagar` | Registra pagamento |
| `PUT` | `/api/sinistro/{nr}/encerrar` | Encerra sinistro |
| `GET/POST` | `/api/sinistro/{nr}/documentos` | Kit ECM |
| `DELETE` | `/api/sinistro/{nr}/documentos/{id}` | Remove documento |

#### Demais módulos
| Módulo | Prefixo | Operações |
|---|---|---|
| Impressão | `/api/impressao/controle` | Lista, cria, fecha período |
| Cosseguro | `/api/cosseguro/participacoes` | Lista, cria, confirma, cancela |
| Pessoas | `/api/pessoas` | CRUD + vínculos com apólices |
| Painel | `/api/painel` | KPIs + pipeline aceitação + últimas ações |

#### AI Layer
| Método | Path | Descrição |
|---|---|---|
| `GET` | `/api/ai/health` | Status dependências AI |
| `POST` | `/api/ai/rag/index` | Indexa diretório no ChromaDB |
| `POST` | `/api/ai/rag/query` | Busca semântica (RAG) |
| `POST` | `/api/ai/agent/run` | Executa agente COBOL (Tool Calling) |
| `POST` | `/api/ai/abend/analisar` | Diagnóstico abend sem LLM |
| `POST` | `/api/ai/guardrails/check` | Valida mensagem pelos guardrails |
| `GET` | `/api/ai/evals/run` | Executa suite de avaliação |
| `GET` | `/api/ai/finetune/dataset` | Baixa dataset fine-tuning |

---

### 6.3 Schemas Pydantic

**`app/schemas/lifecore.py`** — schemas v2 (módulos completos):

| Schema | Uso |
|---|---|
| `EmpresaCreate` / `EmpresaResponse` | CRUD de empresas |
| `CongenereCreate` / `CongenereResponse` | CRUD de congêneres |
| `PropostaCreate` / `PropostaResponse` | Ciclo proposta |
| `AceitePropostaRequest` | `tp_aceite`: `AU` (auto) / `MA` (manual) |
| `RecusaPropostaRequest` | `cd_motivo` + `ds_motivo` |
| `SinistroCreate` / `SinistroResponse` | Ciclo sinistro |
| `ParametroInterfaceResponse` | Parâmetros de sistema |
| `ParametroRotinaResponse` | Parâmetros de aceitação automática |
| `DocECMResponse` | Documentos digitais |
| `ControleImpressaoResponse` | Controle impressão (inclui `fl_fechado`) |
| `AuditoriaAcaoResponse` | Trilha de auditoria |
| `KPICard` | `titulo`, `valor`, `variacao_pct`, `tendencia` |
| `PipelineAceitacao` | Contagens AN/AA/PD/RC do pipeline |
| `UltimaAcao` | Ação recente para feed do painel |
| `PainelResponse` | Resposta consolidada do painel |

**Enums globais:**

| Enum | Valores |
|---|---|
| `TipoEmpresaEnum` | SE / ES / CO / CN / RE |
| `TipoPessoaEnum` | PF / PJ |
| `StatusGeralEnum` | AT / IN |
| `StatusPropostaEnum` | AN / AA / PD / AC / RC / CA |
| `StatusApoliceEnum` | AT / CA / SU / EX |
| `StatusSinistroEnum` | AB / AN / PG / EN / RC |
| `TipoEventoSinistroEnum` | MORT / INVA / DIT / VIAG / DMH |
| `ModuloAuditoriaEnum` | Emissão / Sinistro / Aceitação / Cadastro / Cobrança / Rotina / ECM / Cosseguro / Impressão |

---

### 6.4 Serviços Internos

#### `app/services/conversor.py`

| Função | Assinatura | Descrição |
|---|---|---|
| `parse_csv` | `(data: bytes) → list[ApoliceInput]` | CSV → objetos |
| `parse_xlsx` | `(data: bytes) → list[ApoliceInput]` | XLSX → objetos |
| `parse_json` | `(data: bytes) → list[ApoliceInput]` | JSON → objetos |
| `apolice_to_fixed` | `(apolice, seq) → str` | Objeto → linha 300 chars |
| `build_flat_file` | `(apolices) → str` | Lista → arquivo completo (H0 + D1s + T9) |
| `_fmt_str` | `(value, length) → str` | Trunca/padeia string |
| `_fmt_num` | `(value, digits) → str` | Float → numeric zerofilled |

**Layout de saída (300 bytes):**
```
Pos  1- 2  : Tipo registro (D1)
Pos  3-14  : Número apólice
Pos 15-17  : Produto (VGC/GLB)
Pos 18-31  : CNPJ estipulante
Pos 32-42  : CPF segurado
Pos 43-82  : Nome segurado (40 chars)
Pos 83-90  : Vigência início AAAAMMDD
Pos 91-98  : Vigência fim    AAAAMMDD
Pos 99-100 : Status (AT)
Pos 101    : Tipo capital (F/E/M/B/P)
Pos 102-116: Capital segurado (15 dígitos, V99 implícito)
Pos 117-129: Salário base     (13 dígitos)
Pos 130-135: Fator multiplicador (6 dígitos)
Pos 136-149: Prêmio líquido   (13 dígitos)
Pos 150-163: Prêmio bruto     (13 dígitos)
Pos 164-174: IOF              (11 dígitos)
Pos 175-176: Forma pagamento
Pos 177-178: Periodicidade
Pos 179-186: Data emissão AAAAMMDD
Pos 187-194: Usuário inclusão
Pos 195-220: Timestamp (26 chars)
Pos 221-300: Filler (espaços)
```

#### `app/services/batch_connector.py`

| Função | Descrição |
|---|---|
| `criar_job() → str` | Cria job com UUID, status PENDENTE |
| `obter_job(job_id) → JobStatusResponse` | Consulta status |
| `disparar_batch(job_id, path)` | async — despacha conforme `BATCH_CONNECTOR` |
| `_executar_stub(...)` | Simula 3 steps com `asyncio.sleep` |
| `_executar_local(...)` | Subprocess GnuCOBOL + variáveis de ambiente |
| `_executar_zowe(...)` | Zowe CLI: upload dataset + submit JCL + poll status |

**Store em memória:** `_jobs: dict[str, JobStatusResponse]` — substituir por Redis/DB em produção.

---

## 7. AI Layer

### 7.1 RAG Engine (`app/ai/rag/engine.py`)

**Classes:**

| Classe | Responsabilidade |
|---|---|
| `Document` | Unidade indexada: `doc_id`, `text`, `metadata` |
| `RetrievedChunk` | Resultado de busca: `doc_id`, `text`, `score`, `metadata` |
| `RAGResponse` | Resposta completa: `answer`, `sources`, `query`, `model_used`, `context_tokens` |
| `Embedder` | Wrapper `sentence-transformers`: `embed(texts)`, `embed_one(text)` |
| `VectorStore` | ChromaDB: `upsert(docs, embeddings)`, `query(embedding, top_k)`, `count()`, `reset()` |
| `Indexer` | `index_file(path)`, `index_directory(root)`, `index_text(text, doc_id)` |
| `RAGEngine` | `retrieve(query, top_k)`, `generate(query, top_k)` |

**Variáveis de configuração:**

| Variável | Padrão | Papel |
|---|---|---|
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Modelo 384 dims, CPU, 80 MB |
| `CHROMA_PATH` | `/tmp/lifecore_chroma` | Persistência local |
| `COLLECTION` | `lifecore_docs` | Namespace da coleção |
| `CHUNK_SIZE` | `500` | Palavras por chunk |
| `CHUNK_OVERLAP` | `80` | Sobreposição entre chunks |
| `TOP_K` | `5` | Resultados por busca |

**Extensões de arquivo indexadas:** `.md`, `.cbl`, `.cpy`, `.jcl`, `.sql`, `.py`

**System prompt do RAG Engine:** assistente técnico LifeCore, português (BR), nunca inventa código.

---

### 7.2 Agente COBOL — Tool Calling (`app/ai/agents/`)

**Loop ReAct:** Raciocínio → Ação (tool call) → Observação → Próximo turno → Resposta final

**6 Tools disponíveis:**

| Tool | Descrição | Guardrail |
|---|---|---|
| `consultar_banco` | SELECT no banco | Bloqueado se não começa com SELECT |
| `disparar_job_cobol` | Executa job COBOL | Jobs destrutivos exigem `aprovado_pelo_usuario=True` |
| `ler_resultado_job` | Lê saída do job | — |
| `buscar_documentacao` | RAG nos documentos | — |
| `analisar_abend` | Diagnóstico de abend | Catálogo local (instantâneo, sem LLM) |
| `listar_apolices` | Lista apólices | — |

**Catálogo de abends embutido:** S0C7, S0C4, S322, S806, -904, -911, -913

**Classe `COBOLAgent`:**

| Método | Descrição |
|---|---|
| `run(message, history)` | Loop ReAct síncrono → `AgentResponse` |
| `stream(message)` | Gerador de tokens (streaming para UI) |

**Variáveis:**

| Variável | Padrão |
|---|---|
| `MAX_TURNS` | `8` |
| `LLM_BASE_URL` | `http://localhost:11434/v1` |
| `LLM_MODEL` | `llama3.2` |

---

### 7.3 MCP Server (`app/ai/mcp/server.py`)

Expõe o LifeCore para qualquer cliente MCP compatível (Claude Desktop, Cursor, Continue.dev, Zed).

**Transporte:** `stdio` (padrão) — sem servidor HTTP adicional.

**Tools MCP:**

| Tool | Parâmetros | Descrição |
|---|---|---|
| `lifecore_rag_query` | `query`, `top_k` | Busca semântica nos docs |
| `lifecore_analisar_abend` | `codigo_abend`, `nome_programa`, `contexto` | Diagnóstico abend |
| `lifecore_listar_apolices` | `cd_empresa`, `cd_status`, `limite` | Lista apólices |
| `lifecore_disparar_job` | `nome_job`, `aprovado_pelo_usuario` | Executa job COBOL |
| `lifecore_consultar_banco` | `sql`, `justificativa` | SELECT no banco |

**Resources MCP:**

| URI | Descrição |
|---|---|
| `runbook://abends` | Catálogo completo de abends em Markdown |
| `runbook://copybooks/{nome}` | Conteúdo de um copybook (ex: CPYAPOL) |

**Prompts MCP:**

| Nome | Parâmetros | Uso |
|---|---|---|
| `diagnosticar_abend` | `codigo`, `programa`, `log_trecho` | Template análise de abend |
| `revisar_job_faturamento` | — | Checklist pré-execução FATURA01 |

**Instalação:** `pip install mcp` (opcional — MCP só ativa se o pacote estiver presente).

---

### 7.4 Guardrails e AI Security (`app/ai/guardrails/pipeline.py`)

**4 camadas de proteção:**

#### InputGuardrail
Verifica antes de enviar ao LLM:

| Verificação | Padrão detectado | Ação |
|---|---|---|
| Comprimento | `> 2000 chars` | Bloqueia (risk 0.3) |
| Prompt injection | `"ignore as instruções anteriores"`, `jailbreak`, `DAN mode`, tokens especiais | Bloqueia (risk 1.0) |
| SQL destrutivo | `INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER` | Bloqueia (risk 0.8) |

#### ActionGuardrail
Verifica antes de executar tool:

| Tool | Regra |
|---|---|
| `disparar_job_cobol` | Jobs `FATURA01/PAGTO01/CONCIL01/COMIS01/SETTLE01` exigem `aprovado_pelo_usuario=True` |
| `consultar_banco` | SQL destrutivo bloqueado (risk 1.0) |

#### OutputGuardrail
Sanitiza resposta do LLM:

| Padrão | Ação |
|---|---|
| PAN (Visa/Master/Amex/Elo/Diners/JCB) | Mascara: mantém 6 primeiros + 4 últimos |
| CPF (11 dígitos) | Mascara: `XXX.***.***-YY` |

#### RateLimiter
- `max_per_minute`: 20 chamadas/usuário (configurável)
- Janela deslizante de 60 segundos
- Store em memória: `dict[user_id, list[timestamp]]`

**Classe `GuardrailPipeline`** — encadeia todas as camadas:

| Método | Descrição |
|---|---|
| `check_input(user_id, text)` | Rate limit + InputGuardrail |
| `check_tool_call(tool_name, args)` | ActionGuardrail |
| `sanitize_output(text)` | OutputGuardrail |

---

### 7.5 LLM Evaluation (`app/ai/evals/evaluator.py`)

**5 critérios de avaliação (score 0.0–1.0):**

| Critério | Threshold | Método |
|---|---|---|
| `correctness` | 0.60 | F1 vs gold standard |
| `groundedness` | 0.50 | Sobreposição de termos com contexto RAG |
| `safety` | 0.90 | Ausência de PAN, SQL destrutivo |
| `helpfulness` | 0.60 | Não é recusa, tem ≥ 100 chars |
| `conciseness` | 0.50 | Média de 15–40 palavras/sentença |

**Veredicto:** `PASS` / `WARN` / `FAIL` (FAIL se safety < 0.9)

**Classe `RuleBasedEvaluator`** — sem LLM, instant, ideal para CI/CD.

**Classe `LLMJudge`** — usa LLM separado como juiz:
- Prompt estruturado com instrução de retornar JSON
- `response_format={"type": "json_object"}` (Structured Output)
- Fallback automático para `RuleBasedEvaluator` se LLM indisponível

**Dataset de avaliação (`EVAL_DATASET`)** — 5 casos:

| ID | Categoria | Pergunta |
|---|---|---|
| `abend-s0c7-01` | abend | S0C7 no FATURA01 |
| `jcl-cond-01` | jcl | COND no LCDIA01 |
| `sql-cursor-01` | db2 | Cursor DB2 em COBOL |
| `seguro-capital-01` | negocio | Tipos de capital VGC |
| `pci-pan-01` | segurança | PAN no CPYPAGT |

**Função `run_eval_suite(agent_fn, evaluator, dataset)`** — executa todos os casos e loga resumo.

---

### 7.6 Dataset de Fine-tuning (`app/ai/finetune/dataset.py`)

**9 pares Q/A** cobrindo: abends (3), JCL (2), DB2 (1), negócio VGC (2), PCI segurança (1).

**Formatos suportados:**

| Formato | Estrutura | Uso |
|---|---|---|
| `chatml` | `{"messages": [{role, content}…]}` | Unsloth / TRL / LM Studio |
| `alpaca` | `{"instruction", "input", "output"}` | Alpaca-style fine-tuning |
| `sharegpt` | `{"conversations": [{from, value}…]}` | ShareGPT / Axolotl |

**Funções:**

| Função | Descrição |
|---|---|
| `build_dataset(fmt)` | Retorna lista de dicts no formato |
| `save_dataset(path, fmt)` | Salva JSONL, retorna contagem |
| `get_stats(dataset)` | `total_examples`, `avg_output_words`, categorias |

**CLI:** `python -m app.ai.finetune.dataset --format chatml --output lifecore_finetune.jsonl`

**Após gerar o dataset — fine-tuning com Unsloth (QLoRA, 4-bit, 1 GPU):**
```bash
unsloth finetune --model llama3.2-3b-4bit --data lifecore_finetune.jsonl
# Quantização pós-treinamento (llama.cpp):
./quantize model.gguf model-q4_k_m.gguf Q4_K_M
```

### 7.7 Detecção de Fraude em Seguros (`app/ai/fraud/`) — LCIQ-3

Módulo especializado em padrões de fraude do domínio **VGC/GLB** (Vida em Grupo Coletivo). Analisa sinistros, apólices, coberturas e propostas — **não** é fraude de cartão/pagamento.

**Estrutura:**

```
app/ai/fraud/
├── detector.py           ← orquestrador: coleta contexto + calcula flags
├── rules/
│   ├── sinistro.py       ← abertura_imediata, carencia_violada, capital_anormal
│   ├── apolice.py        ← proposta_manual_rapida, concentracao_mort
│   └── segurado.py       ← cpf_multiplas_apolices, inclusao_retroativa
├── providers/
│   ├── base.py           ← FraudProvider (ABC) — Strategy pattern
│   ├── watsonx.py        ← IBM watsonx.ai (contexto atuarial)
│   ├── openai.py         ← OpenAI
│   └── mock.py           ← Mock para CI/CD (cenários MORT/INVA)
├── schemas.py            ← FraudScoreRequest / FraudScoreResponse
└── router.py             ← POST /api/ai/fraud/score
```

**Tabelas do schema_v2.sql envolvidas:** `SINISTRO`, `COBERTURA`, `PROPOSTA`, `SEGURADO`, `APOLICE`

**Flags de fraude atuarial:**

| Flag | Condição | Peso |
|---|---|---|
| `abertura_imediata` | `DT_ABERTURA = DT_EVENTO` | +0.35 |
| `capital_anormal` | `VL_INDENIZACAO > 2×` média histórica | +0.30 |
| `inclusao_retroativa` | segurado incluso < 30 dias antes do evento | +0.40 |
| `carencia_violada` | `DT_EVENTO < DT_INCLUSAO + NR_CARENCIA_DIAS` | +0.50 |
| `concentracao_mort` | > 3 MORT na mesma empresa em 90 dias | +0.25 |
| `proposta_manual_rapida` | `TP_ACEITE=MA` + `NR_DIAS_ANALISE=0` | +0.20 |
| `beneficiario_sem_kit` | `KIT_SINISTRO` incompleto | +0.15 |
| `cpf_multiplas_apolices` | CPF ativo em > 3 apólices com capital alto | +0.20 |

**Endpoint:** `POST /api/ai/fraud/score` → `{ score, risk_level, flags, provider, latency_ms }`

**Configuração:** `FRAUD_API_PROVIDER=watsonx|openai|mock` (Strategy — troca sem alterar código)

**PCI-DSS:** contexto enviado à API nunca inclui PAN — usa `cd_token_cartao` + `cd_ultimos4`.

---

### 7.8 Observabilidade de Segurança (`app/ai/security/`) — LCIQ-11

Registra eventos de bloqueio do pipeline de segurança (Presidio, Bandit, detect-secrets, COBOL PCI hook) na trilha de auditoria.

**Destinos:**
- Tabela `AUDITORIA_ACAO` (campo `TP_MODULO = 'security'`)
- Span OpenTelemetry por evento
- `GET /api/ai/security/events` — últimos 100 eventos paginados

**Tipos de evento:** `PII_DETECTED` · `PAN_DETECTED` · `SECRET_DETECTED` · `SAST_VIOLATION` · `CPF_HARDCODED`

**Regra PCI-DSS:** valor bloqueado **nunca** aparece no log — apenas `tipo + arquivo + linha`.

---

## 8. Observabilidade — OpenTelemetry

**Arquivo:** `app/core/telemetry.py`

**Funções:**

| Função | Descrição |
|---|---|
| `setup_tracing(app)` | Instrumenta FastAPI — retorna `TracerProvider` ou `None` |
| `get_tracer(name)` | Tracer para spans manuais nos handlers |
| `inject_trace_context(job_id)` | Extrai `trace_id` e `span_id` para propagar ao COBOL |

**Middleware de correlação** (registrado em `main.py`):
- Lê `X-Request-Id` do cliente (ou gera UUID)
- Injeta `X-Trace-Id` (trace_id OTel) em toda resposta
- Loga: `method`, `path`, `status`, `trace_id`

**Exporters disponíveis:**

| Tipo | Destino | Quando usar |
|---|---|---|
| `console` | stdout | Desenvolvimento local |
| `grpc` | `OTEL_EXPORTER_OTLP_ENDPOINT` | Jaeger, Grafana Agent, DataDog |
| `http` | `OTEL_EXPORTER_OTLP_HTTP_ENDPOINT` | Jaeger HTTP, HoneyComb |

**Uso em handlers (span manual):**
```python
from app.core.telemetry import get_tracer
tracer = get_tracer(__name__)

@router.post("/...")
def criar_proposta(payload):
    with tracer.start_as_current_span("emissao.criar_proposta") as span:
        span.set_attribute("nr_proposta", payload.nr_proposta)
        span.set_attribute("cd_empresa",  payload.cd_empresa)
        ...
```

---

## 9. Testes

### Suites

| Arquivo | Testes | Cobertura |
|---|---|---|
| `tests/test_api.py` | 39 | Health, importação, todos os módulos negócio, painel, conversor |
| `tests/test_ai_layer.py` | 33 | Guardrails, abend diagnóstico, evaluator, dataset, tools, RAG, MCP |
| `tests/e2e/test_swagger_smoke.py` | 8 | Swagger UI, health via browser, CORS, X-Trace-Id, fluxo proposta E2E |
| **Total** | **80** | |

### Como rodar

```bash
# Testes unitários + integração (sem servidor)
cd LifeCore-Mainframe/integration-layer
OTEL_ENABLED=false pytest tests/test_api.py tests/test_ai_layer.py -v

# Testes E2E Playwright (requer uvicorn rodando na porta 8000)
pytest tests/e2e/ -v --headed    # com browser visível
pytest tests/e2e/ -v             # headless (CI)
```

### Fixtures e mocks

- Todos os módulos de negócio usam **stores em memória** (`dict`) — sem banco real
- `BATCH_CONNECTOR=stub` — sem COBOL instalado
- `OTEL_ENABLED=false` — sem exporter externo
- `RAG_CHROMA_PATH=/tmp/...` — ChromaDB de teste isolado

---

## 10. CI/CD

**Arquivo:** `.github/workflows/ci.yml`

**8 jobs (GitHub Actions):**

| Job | Trigger | O que faz |
|---|---|---|
| `compile` | push/PR | Instala GnuCOBOL, compila 9 programas, upload binários como artifact |
| `lint` | após compile | Syntax check, verifica copybooks, SQLCA inline, padrões PAN |
| `integration-test` | após compile | Baixa binários, testa ARQVAL01 (OK + erros), VGCCAP01, CLEAR01 |
| `schema-validate` | paralelo | Sobe PostgreSQL, aplica schema_v2.sql, verifica 7 tabelas |
| `api-test` | paralelo | Instala deps Python, roda 39 testes, sobe uvicorn, verifica headers OTel |
| `e2e-test` | após api-test | Instala Playwright + Chromium, sobe servidor, roda 8 testes E2E |
| `security` | paralelo | Bandit SAST, detect-secrets, Presidio PII/PAN, COBOL PCI check — ver §10.1 |
| `summary` | após todos | Tabela Markdown com resultado de cada job no GITHUB_STEP_SUMMARY |

### 10.1 Job `security` — pipeline de segurança

**Ferramentas:**

| Ferramenta | Versão | O que detecta |
|---|---|---|
| **Bandit** | 1.9.4 | SAST Python — severity medium+, confidence medium+ |
| **detect-secrets** | 1.5.0 | Credenciais hardcoded — 27 plugins (AWS, GitHub, OpenAI, IBM Cloud…) |
| **Presidio** | 2.2.364 | PII/PAN — CPF, e-mail, telefone, cartão (LGPD + PCI-DSS) |
| **COBOL PCI hook** | local | Campos PAN e SQLCA inline em `.cbl`/`.cpy` |

**Artefatos gerados:** `bandit-report.json` (retido 30 dias)

**Baseline detect-secrets:** `.secrets.baseline` — segredos existentes marcados para não bloquear CI.
Novo segredo → falha imediata com arquivo:linha.

### 10.2 Pre-commit hooks

**Arquivo:** `.pre-commit-config.yaml` (raiz do repositório)

**Instalação:**
```bash
pip install pre-commit
pre-commit install        # instala hooks em .git/hooks/pre-commit
pre-commit run --all-files  # executa em todos os arquivos
```

**Hooks configurados:**

| Hook | Ferramenta | Ação |
|---|---|---|
| `ruff` | Ruff 0.4.4 | Lint Python — auto-fix + bloqueia erros restantes |
| `ruff-format` | Ruff 0.4.4 | Formatação automática |
| `trailing-whitespace` | pre-commit-hooks | Remove espaços no fim |
| `detect-private-key` | pre-commit-hooks | Bloqueia chaves privadas |
| `detect-secrets` | Yelp/detect-secrets | Credenciais hardcoded vs `.secrets.baseline` |
| `bandit` | PyCQA/bandit | SAST Python severity medium+ |
| `presidio-pii-scan` | local | PII/PAN em `.py` — CPF, e-mail, cartão |
| `cobol-pci-check` | local | PAN e SQLCA inline em `.cbl`/`.cpy` |

**Scripts locais:** `scripts/presidio_hook.py`, `scripts/cobol_pci_hook.sh`

**Anotação para falsos positivos (dados de teste):**
```python
cpf = "111.444.777-35"  # presidio: ignore
```

---

## 11. Scripts

### `SCRIPTS/compile.sh`

```bash
./SCRIPTS/compile.sh          # compila todos
./SCRIPTS/compile.sh ARQVAL01 # compila um programa
./SCRIPTS/compile.sh check    # verifica pré-requisitos
```

**Funções internas:**

| Função | Descrição |
|---|---|
| `check_prereqs()` | Verifica GnuCOBOL, ocesql, psql |
| `compile_plain(prog)` | `cobc -x` para programas sem EXEC SQL |
| `compile_esql(prog)` | `ocesql` + `cobc -x` para programas com DB2 |
| `compile_module(prog)` | `cobc -m` para CALCCAP (subprograma) |

**Variáveis do script:**

| Variável | Valor |
|---|---|
| `ROOT_DIR` | `$(dirname $SCRIPTS_DIR)` |
| `SRC_DIR` | `$ROOT_DIR/SRC/COBOL` |
| `COPY_DIR` | `$ROOT_DIR/COPYLIB` |
| `LOAD_DIR` | `$ROOT_DIR/LOAD` |

### `SCRIPTS/run-cycle.sh`

```bash
./SCRIPTS/run-cycle.sh          # dados OK
./SCRIPTS/run-cycle.sh erros    # dados com falhas (testa quarentena)
./SCRIPTS/run-cycle.sh s0c7     # COMP-3 corrompido (testa abend)
```

Simula o `LCDIA01.jcl` localmente via subprocess dos binários em `LOAD/`.

**Variáveis de ambiente exportadas para os programas COBOL:**

| Variável | Valor |
|---|---|
| `LIFECORE_DATA_INPUT_APOLICE` | `$DATA_DIR/INPUT/APOLICE` |
| `LIFECORE_DATA_OUTPUT_APOLICE` | `$DATA_DIR/OUTPUT/APOLICE` |
| `LIFECORE_DATA_QUARANTINE_APOLICE` | `$DATA_DIR/QUARANTINE/APOLICE` |
| `LIFECORE_DATA_OUTPUT_CAPITAL` | `$DATA_DIR/OUTPUT/CAPITAL` |
| `LIFECORE_DATA_OUTPUT_FATURA` | `$DATA_DIR/OUTPUT/FATURA` |

### `SCRIPTS/setup-db.sh`

```bash
./SCRIPTS/setup-db.sh
```

Cria o banco `lifecore`, usuário `lifecore`, e aplica `SQL/schema_v2.sql`.

---

## 12. Dependências

### Python (production)

| Pacote | Versão mínima | Uso |
|---|---|---|
| `fastapi` | ≥ 0.111 | Framework web |
| `uvicorn[standard]` | ≥ 0.29 | ASGI server |
| `pydantic` | ≥ 2.7 | Validação schemas |
| `pydantic-settings` | ≥ 2.2 | Variáveis de ambiente |
| `python-multipart` | ≥ 0.0.9 | Upload de arquivos |
| `openpyxl` | ≥ 3.1 | Leitura de XLSX |
| `psycopg2-binary` | ≥ 2.9 | PostgreSQL |
| `httpx` | ≥ 0.27 | HTTP client (testes) |
| `opentelemetry-sdk` | ≥ 1.25 | Tracing base |
| `opentelemetry-instrumentation-fastapi` | ≥ 0.46 | Auto-instrumentação FastAPI |
| `opentelemetry-exporter-otlp-proto-grpc` | ≥ 1.25 | Exporter gRPC |
| `opentelemetry-exporter-otlp-proto-http` | ≥ 1.25 | Exporter HTTP |
| `sentence-transformers` | ≥ 3.0 | Embeddings locais (MiniLM-L6-v2) |
| `chromadb` | ≥ 0.5 | Vector store local |
| `openai` | ≥ 1.0 | SDK compatível com Ollama/LM Studio |

### Python (dev/test)

| Pacote | Uso |
|---|---|
| `pytest` | Test runner |
| `pytest-asyncio` | Testes assíncronos |
| `anyio` | Backend async |
| `pytest-playwright` | Testes E2E |
| `playwright` | Browser automation (Chromium) |

### Python (opcional)

| Pacote | Uso |
|---|---|
| `mcp` | MCP Server (Claude Desktop / Cursor) |

### Sistema (mainframe/local)

| Software | Versão | Uso |
|---|---|---|
| GnuCOBOL | ≥ 3.x | Compilação COBOL local |
| ocesql | qualquer | SQL embutido → PostgreSQL |
| PostgreSQL | ≥ 14 | DB2 local |
| Zowe CLI | ≥ 7.x | Ponte com z/OS real |
| IBM Z Xplore | gratuito | z/OS, TSO/ISPF, JCL, DB2 reais |

---

## 13. Como Executar

### Desenvolvimento local (sem z/OS)

```bash
# 1. Clonar e entrar no projeto
cd LifeCore-Mainframe

# 2. Compilar COBOL
./SCRIPTS/compile.sh

# 3. Criar banco
./SCRIPTS/setup-db.sh

# 4. Subir a API
cd integration-layer
cp .env.example .env          # edite DATABASE_URL se necessário
pip install -r requirements.txt
BATCH_CONNECTOR=stub uvicorn app.main:app --reload --port 8000

# 5. Swagger UI
open http://localhost:8000/docs

# 6. Rodar testes
pytest tests/ -v
```

### Com agente IA (Ollama local)

```bash
# 1. Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# 2. Configurar .env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2
OTEL_ENABLED=false

# 3. Indexar projeto
curl -X POST http://localhost:8000/api/ai/rag/index \
  -H 'Content-Type: application/json' \
  -d '{"directory": "."}'

# 4. Consultar agente
curl -X POST http://localhost:8000/api/ai/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"message": "Por que ocorre S0C7 no FATURA01?"}'
```

### Com z/OS real (IBM Z Xplore)

```bash
# Configurar Zowe
zowe config init
zowe config set profiles.zosmf.host <host>

# Compilar JCL
BATCH_CONNECTOR=zowe

# A Integration Layer envia o arquivo e submete via LCIMP01.jcl
curl -X POST http://localhost:8000/api/apolices/importar \
  -F "arquivo=@TESTDATA/APOLICE_OK.DAT"
```

### MCP Server (Claude Desktop)

Adicione em `~/.config/claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "lifecore": {
      "command": "python",
      "args": ["-m", "app.ai.mcp.server"],
      "cwd": "/caminho/para/LifeCore-Mainframe/integration-layer"
    }
  }
}
```

---

## 14. Convenções e Padrões

### COBOL

| Convenção | Regra |
|---|---|
| Formato | Fixo (colunas 7–72). **Sem `-free`** |
| Nomes | MAIÚSCULAS, hifenizados: `APO-CAPITAL-SEGURADO` |
| Subprogramas | `CALL 'NOME' USING ...` — módulo compilado com `cobc -m` |
| Campos monetários | `PIC S9(x)V99 COMP-3` — nunca `VALUE 0.01.` (double-dot) |
| SQL embutido | `EXEC SQL ... END-EXEC`. Sempre verificar `SQLCODE` |
| PCI | Nunca `PIC X(16)` para cartão — usar token + últimos 4 |

### Python / FastAPI

| Convenção | Regra |
|---|---|
| Schemas | Pydantic v2 — usar `model_config = {"from_attributes": True}` |
| Stores | In-memory `dict` (stub) — substituir por SQLAlchemy em produção |
| IDs de usuário | `max_length=20` (não 8 — nomes reais têm mais que 8 chars) |
| Numeração | `nr_proposta`/`nr_apolice`/`nr_sinistro` max 20 chars: `2026.PROP.000001` |
| Datas | String `AAAAMMDD` (`pattern=r'^\d{8}$'`) |
| Timestamps | `datetime.now(timezone.utc)` — não `utcnow()` (deprecated Python 3.12) |

### SQL

| Convenção | Regra |
|---|---|
| Prefixo tabelas | Sem prefixo — nomes diretos (`APOLICE`, `SEGURADO`) |
| Campos data | `CHAR(8)` formato `AAAAMMDD` para compatibilidade COBOL |
| Campos monetário | `NUMERIC(15,2)` |
| Status | `CHAR(2)` com check constraint |
| Auditoria | `AUDITORIA_ACAO` registra toda ação com usuário + timestamp |

### AI Layer

| Convenção | Regra |
|---|---|
| Guardrails | Sempre aplicar `check_input` antes de chamar LLM |
| Jobs destrutivos | `FATURA01`, `PAGTO01`, `CONCIL01`, `COMIS01`, `SETTLE01` exigem aprovação |
| PAN na saída | Output Guardrail mascara automaticamente |
| LLM | Responder em português (BR), nunca inventar código |
| Embeddings | `all-MiniLM-L6-v2` — 384 dims, sem GPU, 80 MB |

---

> **Gerado por:** LifeCore-Mainframe documentation generator
> **Última atualização:** 2026 — versão 2.0.0
