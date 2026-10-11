# AGENTS.md — Base de Conhecimento dos Agentes LifeCore IQ

> Este documento é a fonte primária de conhecimento para o agente 🤖 Knowledge/RAG.
> Descreve responsabilidades, escopo, artefatos, critérios de aceite e padrões operacionais
> de cada um dos 18 agentes do LifeCore IQ.
>
> **Convenção de atualização:** sempre que um agente encerrar uma Epic ou resolver um incidente
> relevante, o agente 🧠 Orquestrador abre uma issue `docs/rag/LCIQ-###-atualizar-agents-md`
> e o agente 🤖 Knowledge/RAG atualiza este arquivo.

---

## Índice

| # | Agente | Slug | Epic prefix |
|---|--------|------|-------------|
| 1 | 🧾 Faturamento | `fat` | `LCIQ-FAT-*` |
| 2 | 🔄 Renovação | `ren` | `LCIQ-REN-*` |
| 3 | 🛠️ Sustentação | `sus` | `LCIQ-SUS-*` |
| 4 | 🚀 Melhoria Contínua | `mlc` | `LCIQ-MLC-*` |
| 5 | 📦 Produto | `prd` | `LCIQ-PRD-*` |
| 6 | 👥 Segurados | `seg` | `LCIQ-SEG-*` |
| 7 | 🤝 Corretagem | `cor` | `LCIQ-COR-*` |
| 8 | 💰 Comissões | `com` | `LCIQ-COM-*` |
| 9 | ⚖️ Sinistros | `sin` | `LCIQ-SIN-*` |
| 10 | 🔄 Conciliação | `cnc` | `LCIQ-CNC-*` |
| 11 | 📁 Arquivos | `arq` | `LCIQ-ARQ-*` |
| 12 | 🔌 Integrações | `int` | `LCIQ-INT-*` |
| 13 | 🔎 Qualidade de Dados | `qdt` | `LCIQ-QDT-*` |
| 14 | 📊 BI/Inteligência | `bia` | `LCIQ-BIA-*` |
| 15 | 🔐 Governança | `gov` | `LCIQ-GOV-*` |
| 16 | 🧪 QA/Testes | `qat` | `LCIQ-QAT-*` |
| 17 | 🤖 Knowledge/RAG | `rag` | `LCIQ-RAG-*` |
| 18 | 🧠 Orquestrador | `orc` | `LCIQ-ORC-*` |

---

## 1 · 🧾 Faturamento (`fat`)

**Responsabilidade:** Geração, validação e fechamento de faturas mensais por estipulante.
Gestão de divergências, aplicação de IPCA e controle de endossos financeiros.

**Artefatos principais:**
- `SRC/COBOL/FATURA01.cbl` — geração de fatura batch
- `app/api/emissao/faturamento.py` — endpoints REST de fatura e IPCA
- `SQL/schema_v2.sql` tabelas: `FATURA`, `FATURA_ITEM`, `TAXA_IPCA`

**Endpoints sob sua responsabilidade:**
- `POST /api/emissao/apolices/{nr}/faturamento` — gera fatura
- `GET  /api/emissao/apolices/{nr}/faturas` — lista faturas
- `GET  /api/emissao/taxas-ipca` — consulta taxa IPCA vigente

**Regras de negócio críticas:**
- Capital segurado é reajustado mensalmente pelo IPCA (índice SUSEP para seguros)
- Fatura só pode ser gerada se apólice estiver com status `AT` (ativa)
- Competência no formato `AAAAMM`; vencimento em `AAAAMMDD`
- Forma de cobrança: `BO` Boleto · `CC` Cartão · `DB` Débito · `PI` PIX

**Branch padrão:** `feat/fat/LCIQ-###-descricao`

---

## 2 · 🔄 Renovação (`ren`)

**Responsabilidade:** Renovação automática e manual de contratos/apólices.
Análise de vencimentos, geração de propostas de renovação e controle de pendências.

**Artefatos principais:**
- `app/api/emissao/config_apolice.py` — renovação de vigência (`PUT /renovar`)
- `app/api/emissao/proposta.py` — geração de nova proposta

**Regras críticas:**
- `dt_fim_vigencia` deve ser posterior a `dt_inicio_vigencia`
- Renovação gera novo registro em `_HISTORICO` com `tp_acao = "RENOVACAO"`
- Apólice cancelada (`CA`) não pode ser renovada — deve gerar nova proposta

**Branch padrão:** `feat/ren/LCIQ-###-descricao`

---

## 3 · 🛠️ Sustentação (`sus`)

**Responsabilidade:** Atendimento a incidentes em produção, análise de causa raiz,
troubleshooting de abends COBOL e correção emergencial.

**Artefatos principais:**
- `LifeCore-Mainframe/RUNBOOK/ABEND-CATALOG.md` — catálogo de falhas
- `TESTDATA/APOLICE_S0C7.DAT` — arquivo com S0C7 injetado para treino

**Catálogo de abends conhecidos:**

| Código | Causa | Ação imediata |
|--------|-------|---------------|
| `S0C7` | Dado numérico inválido em campo COMP-3 | Verificar arquivo de entrada; campo com lixo binário |
| `S0C4` | Violação de endereçamento / ponteiro inválido | Analisar DUMP; verificar subscrito de tabela |
| `S322` | Estouro de tempo de CPU (loop infinito) | Cancelar job; revisar lógica de iteração |
| `S806` | Programa não encontrado na LOADLIB | Verificar STEPLIB/JOBLIB; recompilar se necessário |
| `SQLCODE -904` | Recurso DB2 indisponível | Aguardar liberação; verificar lock com DBA |
| `SQLCODE -911` | Deadlock — transação cancelada pelo DB2 | Retry automático; revisar ordem de acesso às tabelas |
| `SQLCODE -913` | Timeout de lock | Aumentar intervalo de commit; fragmentar batch |

**Branch padrão:** `fix/sus/LCIQ-###-descricao`

---

## 4 · 🚀 Melhoria Contínua (`mlc`)

**Responsabilidade:** Identificar oportunidades de melhoria técnica e de processo.
Registrar tech debt, propor refatorações e acompanhar sua implementação.

**Tipo de issue:** `Improvement` no Jira

**Critério de registro:** qualquer padrão recorrente de incidente, código duplicado,
tempo de processamento batch acima de SLA ou feedback de outro agente.

**Branch padrão:** `chore/mlc/LCIQ-###-descricao`

---

## 5 · 📦 Produto (`prd`)

**Responsabilidade:** Catálogo de produtos, planos, coberturas, benefícios e parametrizações.
Motor de capital parametrizável para VGC e GLB.

**Tipos de capital suportados:**

| Código | Nome | Cálculo |
|--------|------|---------|
| `F` | Fixo | `vl_capital` definido na apólice |
| `E` | Escalonado | Capital varia por faixa etária |
| `M` | Múltiplo salarial | `vl_salario × nr_fator_mult` |
| `B` | Por faixa | Capital por faixa de salário |
| `P` | Por perfil/cargo | Capital por nível hierárquico |

**Artefatos principais:**
- `SRC/COBOL/VGCCAP01.cbl` — cálculo de capital segurado
- `SRC/COBOL/CALCCAP.cbl` — módulo reutilizável de cálculo

**Branch padrão:** `feat/prd/LCIQ-###-descricao`

---

## 6 · 👥 Segurados (`seg`)

**Responsabilidade:** Cadastro de segurados, movimentações (INC/EXC/CAP/SUS/REA),
elegibilidade, beneficiários e motor de críticas.

**Motor de Críticas — Catálogo completo:**

| Código | Severidade | Regra |
|--------|-----------|-------|
| `E001` | BLOQ | CPF com dígito verificador inválido (algoritmo Receita Federal) |
| `E002` | BLOQ | CPF com formato inválido (≠ 11 dígitos ou todos iguais) |
| `E003` | BLOQ | CPF cancelado/suspenso na Receita Federal |
| `E004` | BLOQ | CPF com nome divergente na RF (possível homônimo) |
| `W039` | ALRT | CPF não localizado na RF (API offline) |
| `E010` | BLOQ | Data de nascimento ausente — obrigatória para INC |
| `E011` | BLOQ | Data de nascimento inválida |
| `E012` | BLOQ | Segurado menor de 14 anos na data de inclusão |
| `W025` | MANU | Segurado com mais de 70 anos — pende liberação manual |
| `E013` | BLOQ | Segurado entre 65–70 anos sem cláusula especial |
| `W026` | ALRT | Faixa de atenção: 60–65 anos |
| `E020` | BLOQ | CPF já possui cobertura ATIVA nesta apólice |
| `W021` | ALRT | CPF com cobertura CANCELADA — reinclusão detectada |
| `E030` | BLOQ | Nome do segurado ausente |
| `W031` | ALRT | Nome do segurado muito curto (< 5 caracteres) |
| `E040` | BLOQ | Data de inclusão ausente |
| `E041` | BLOQ | Data de inclusão inválida |
| `W042` | ALRT | Inclusão retroativa > 30 dias |
| `W043` | ALRT | Inclusão futura > 60 dias |

**Tipos de movimentação:** `INC` Inclusão · `EXC` Exclusão · `CAP` Alteração de capital · `SUS` Suspensão · `REA` Reativação

**Artefatos principais:**
- `app/services/criticas_segurado.py` — motor de críticas
- `app/services/movimentacao_segurados.py` — parser de planilha (CSV/XLSX)
- `app/api/emissao/importacao_movimentacao.py` — endpoint de importação
- `app/static/portal.html` — Portal do Corretor

**Branch padrão:** `feat/seg/LCIQ-###-descricao`

---

## 7 · 🤝 Corretagem (`cor`)

**Responsabilidade:** Cadastro de corretores, vínculos empresa-corretora,
produção, arquivos de corretagem e relacionamento operacional.

**Artefatos principais:**
- `app/api/corretagem/corretagem.py`

**Branch padrão:** `feat/cor/LCIQ-###-descricao`

---

## 8 · 💰 Comissões (`com`)

**Responsabilidade:** Cálculo, conferência, divergências e pagamentos de comissão.

**Artefatos principais:**
- `SRC/COBOL/COMIS01.cbl` — cálculo batch de comissões

**Branch padrão:** `feat/com/LCIQ-###-descricao`

---

## 9 · ⚖️ Sinistros (`sin`)

**Responsabilidade:** Abertura, análise, documentação, pendências, acompanhamento de sinistros
e **detecção de fraude atuarial em VGC/GLB**.

**Artefatos principais:**
- `app/api/sinistro/sinistro.py`
- `app/api/sinistro/kit_ecm.py` — documentação ECM
- `app/ai/fraud/` — motor de detecção de fraude em sinistros (LCIQ-3)

**Módulo de fraude — flags atuariais monitoradas:**

| Flag | Condição |
|------|----------|
| `abertura_imediata` | `DT_ABERTURA = DT_EVENTO` |
| `capital_anormal` | `VL_INDENIZACAO > 2×` média histórica da empresa |
| `inclusao_retroativa` | Segurado incluso < 30 dias antes do evento |
| `carencia_violada` | `DT_EVENTO < DT_INCLUSAO + NR_CARENCIA_DIAS` |
| `concentracao_mort` | > 3 MORT na mesma empresa em 90 dias |
| `proposta_manual_rapida` | `TP_ACEITE=MA` + `NR_DIAS_ANALISE=0` |

> ⚠️ Fraude de seguros ≠ fraude de cartão. O módulo analisa `SINISTRO`, `COBERTURA`, `PROPOSTA` e `SEGURADO` — não `PAGAMENTO` ou `CONCILIACAO`.

**Branch padrão:** `feat/sin/LCIQ-###-descricao`

---

## 10 · 🔄 Conciliação (`cnc`)

**Responsabilidade:** Comparar bases faturado × pago, identificar divergências,
acompanhar regularização, processar clearing e liquidação de cartão.

**Fluxo de pagamento por cartão:**
```
Pagador → Estipulante → Adquirente → Bandeira → Emissor
   AUTORIZAÇÃO (ISO 8583: 0100/0110)
       → CAPTURA
           → COMPENSAÇÃO (arquivo clearing batch)
               → LIQUIDAÇÃO (agenda de recebíveis)
                   → CONCILIAÇÃO → DISPUTAS (chargeback)
```

**Artefatos principais:**
- `SRC/COBOL/CONCIL01.cbl` — conciliação faturado × pago
- `SRC/COBOL/CLEAR01.cbl` — leitura do arquivo de clearing
- `SRC/COBOL/SETTLE01.cbl` — conciliação de liquidação
- `SRC/COBOL/DISPUT01.cbl` — tratamento de chargebacks

**Regra PCI:** nunca armazenar PAN completo. Usar token + últimos 4 dígitos.
Campo `cd_token_cartao` + `cd_ultimos4` na tabela `PAGAMENTO` (copybook `CPYPAGT`).

**Branch padrão:** `feat/cnc/LCIQ-###-descricao`

---

## 11 · 📁 Arquivos (`arq`)

**Responsabilidade:** Importação, validação, processamento e rejeição de arquivos batch.
Gestão de GDGs, quarentena de erros e controle de reprocessamento.

**Artefatos principais:**
- `SRC/COBOL/ARQVAL01.cbl` — validação de arquivo de empresa
- `JCL/LCDIA01.jcl` — ciclo diário (13 steps)
- `JCL/LCIMP01.jcl` — importação de arquivo
- `COPYLIB/CPYERRO.cpy` — layout do registro de quarentena

**GDG (Generation Data Groups):**
```
LIFECORE.SRC.COBOL    fontes COBOL
LIFECORE.COPYLIB      layouts (copybooks)
LIFECORE.JCL          jobs
LIFECORE.PROCLIB      procedures
LIFECORE.LOAD         executáveis
LIFECORE.DATA.*       arquivos de entrada/saída (GDG)
```

**Return codes padrão:**
- `0` — Sucesso total
- `4` — Aviso (processado com advertências)
- `8` — Erro recuperável (step seguinte executado com restrições)
- `12` — Erro grave (steps dependentes cancelados)
- `16` — Abend / falha crítica

**Branch padrão:** `feat/arq/LCIQ-###-descricao`

---

## 12 · 🔌 Integrações (`int`)

**Responsabilidade:** APIs REST, eventos, arquivos de interface, integração com i4Pro
e outros sistemas externos.

**Artefatos principais:**
- `app/main.py` — FastAPI v2.1.0, 22+ routers
- `app/services/batch_connector.py` — conector stub/local/Zowe
- `app/api/importacao.py` — importação via API

**Camadas de integração:**
```
z/OS batch (COBOL/JCL) ──► arquivos fixos ──► Integration Layer (FastAPI)
                                                      │
                                          ┌───────────┴────────────┐
                                     API REST              Eventos futuros
                                   (JSON/HTTP)             (Kafka — spike)
```

**Branch padrão:** `feat/int/LCIQ-###-descricao`

---

## 13 · 🔎 Qualidade de Dados (`qdt`)

**Responsabilidade:** Detecção de inconsistências, duplicidades, campos incompletos
e problemas de integridade referencial.

**Checks recorrentes:**
- CPF duplicado em apólices distintas (E020 cross-apólice)
- CNPJ de empresa sem vínculo com corretora
- Coberturas sem capital definido
- Faturas sem itens

**Branch padrão:** `feat/qdt/LCIQ-###-descricao`

---

## 14 · 📊 BI/Inteligência (`bia`)

**Responsabilidade:** Indicadores operacionais, tendências, KPIs e análises.

**KPIs principais:**
- Sinistralidade = `vl_sinistros_pagos / vl_premios_arrecadados`
- Taxa de renovação = `apólices renovadas / apólices vencidas`
- Tempo médio de processamento batch (por step do LCDIA01)
- Divergências de conciliação por competência

**Branch padrão:** `feat/bia/LCIQ-###-descricao`

---

## 15 · 🔐 Governança (`gov`)

**Responsabilidade:** Auditoria, permissões, rastreabilidade, conformidade regulatória
e **observabilidade do pipeline de segurança** (LCIQ-11).

**Frameworks regulatórios:**
- **LGPD** — dados pessoais (CPF, nome, data nasc.) com log de acesso e mascaramento
- **SUSEP** — regulamentação de seguros de vida em grupo
- **PCI-DSS** — dados de cartão: nunca armazenar PAN; usar tokenização
- **Banco Central** — clearing e liquidação de pagamentos

**RACF (z/OS):** perfis por função (operador batch, DBA, auditor).
Mapeado ao RBAC da Integration Layer (`app/auth/`).

**Trilha de auditoria:** toda alteração de apólice registrada em `_HISTORICO`
com `tp_acao`, `ds_valor_antes`, `ds_valor_depois`, `id_usuario`, `dt_hora_acao`.

**Pipeline de segurança (pre-commit + CI/CD):**
- `Presidio 2.2.364` — detecção de PII/PAN em código Python (LGPD + PCI-DSS)
- `Bandit 1.9.4` — SAST Python, severity medium+
- `detect-secrets 1.5.0` — credenciais hardcoded (27 plugins)
- `scripts/cobol_pci_hook.sh` — campos PAN e SQLCA inline em COBOL
- Eventos de bloqueio registrados em `AUDITORIA_ACAO` via `app/ai/security/events.py`

**Tipos de evento de segurança:** `PII_DETECTED` · `PAN_DETECTED` · `SECRET_DETECTED` · `SAST_VIOLATION` · `CPF_HARDCODED`

**Branch padrão:** `chore/gov/LCIQ-###-descricao`

---

## 16 · 🧪 QA/Testes (`qat`)

**Responsabilidade:** Validação de regras de negócio, testes automatizados,
testes de regressão e injeção de falhas para treinamento de causa raiz.

**Estado atual dos testes:**
- **252 testes passando** (pytest, Python 3.12)
- Cobertura mínima aceita: **80%**
- Suítes: `test_api`, `test_auth`, `test_faturamento`, `test_movimentacao`,
  `test_criticas`, `test_config_apolice`, `test_corretagem`

**CPFs válidos para testes (dígito verificador correto):**
```
11144477735  52998224725  12345678577  98765432100
55566677720  10020030088  11122233396  44455566619
77788899941  22233344405  55577788889  33445566062
```

**Falhas injetadas para treino:**
- `TESTDATA/APOLICE_S0C7.DAT` — campo COMP-3 corrompido → provoca S0C7
- CPF inválido na planilha → provoca E001/E002 no motor de críticas

**CI/CD:** `.github/workflows/ci.yml` — 8 jobs: compile · lint · integration-test · schema-validate · api-test · e2e-test · **security** · summary

**Pre-commit:** `.pre-commit-config.yaml` — ruff · detect-secrets · bandit · presidio-pii-scan · cobol-pci-check

**Branch padrão:** `fix/qat/LCIQ-###-descricao`

---

## 17 · 🤖 Knowledge/RAG (`rag`)

**Responsabilidade:** Manutenção da base de conhecimento (este documento),
consulta a regras de negócio, análise assistida de causa raiz com IA.

**Fontes de conhecimento:**
- `AGENTS.md` — este arquivo
- `RUNBOOK/ABEND-CATALOG.md` — catálogo de abends
- `DOCS.md` — documentação técnica da Integration Layer
- `LifeCore-Mainframe/SQL/schema_v2.sql` — modelo de dados
- Issues fechadas do Jira com label `knowledge`

**Atualização:** após cada Sprint Review, revisar e atualizar `AGENTS.md`
com novos runbooks, regras descobertas e decisões técnicas relevantes.

**Branch padrão:** `docs/rag/LCIQ-###-descricao`

---

## 18 · 🧠 Orquestrador (`orc`)

**Responsabilidade:** Distribuição de tarefas entre agentes, coordenação de dependências,
Sprint Planning, gestão de impedimentos e release planning.

**Fluxo de distribuição:**
```
Demanda recebida
    → Orquestrador classifica (Epic + tipo + agente)
    → Cria issue Jira com cd_agente preenchido
    → Agente move para "Em Análise"
    → Orquestrador monitora via JQL: issues paradas > 3 dias
    → Sprint Review: consolida métricas do dashboard
```

**JQL de monitoramento:**
```jql
project = LCIQ AND status = "Em Desenvolvimento" AND updated <= -3d
project = LCIQ AND labels = "ci-failed" AND status != Done
project = LCIQ AND issuetype = Bug AND priority = Critical AND assignee is EMPTY
```

**Branch padrão:** `chore/orc/LCIQ-###-descricao`

---

## Padrão de Commit

```
{LCIQ-###}: {verbo no imperativo} {o que foi feito}

Exemplos:
LCIQ-042: adicionar ciclo de faturamento com IPCA
LCIQ-091: corrigir CPFs inválidos nos testes de movimentação
LCIQ-115: implementar upload CSV no Portal do Corretor
LCIQ-203: corrigir S0C7 em FATURA01 por COMP-3 corrompido
```

---

## Glossário

| Termo | Definição |
|-------|-----------|
| Apólice | Contrato de seguro entre seguradora e estipulante |
| Estipulante | Empresa contratante do seguro coletivo |
| Segurado | Funcionário coberto pela apólice |
| Cobertura | Registro individual de um segurado em uma apólice |
| Endosso | Alteração contratual (inclusão, exclusão, alteração de capital) |
| Competência | Mês de referência do faturamento (formato `AAAAMM`) |
| VGC | Vida em Grupo Coletivo |
| GLB | Global Life Benefits |
| COMP-3 | Formato packed decimal do COBOL (causa S0C7 se corrompido) |
| GDG | Generation Data Group — versionamento de datasets no z/OS |
| PAN | Primary Account Number — número do cartão (nunca armazenar) |
| RACF | Resource Access Control Facility — segurança do z/OS |
| IPCA | Índice de Preços ao Consumidor Amplo — indexador de seguros (SUSEP) |
