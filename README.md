# LifeCore Cobol — LifeCore IQ

> Plataforma de seguros de vida em grupo com camada Legacy Core (z/OS · COBOL · JCL · DB2),
> Integration Layer (FastAPI), AI Layer (RAG · Agentes) e Portal do Corretor (Next.js).

---

## Visão da Arquitetura

```
                     LIFECORE IQ (Next.js / FastAPI)
                               │
                        INTEGRATION LAYER
                    (arquivos, eventos, API REST)
                               │
 ┌─────────────────────────────┴──────────────────────────────┐
 │                  LEGACY CORE (z/OS)                        │
 │                                                            │
 │  TSO/ISPF ── datasets (PDS / sequenciais / VSAM / GDG)     │
 │                                                            │
 │  JCL ──► Scheduler batch ──► Programas COBOL ──► DB2       │
 │                                                            │
 │  Segurança: RACF │ Logs: SYSOUT/SDSF │ Abends/Dumps        │
 └─────────────────────────────┬──────────────────────────────┘
                               │
                    Data Platform / Quality Intelligence (AI)
```

---

## Estrutura do Repositório

```
lifecore-cobol/
├── README.md                     ← este arquivo
├── AGENTS.md                     ← knowledge base dos 18 agentes
├── LifeCore-Mainframe/
│   ├── COPYLIB/                  ← 8 copybooks (CPYAPOL, CPYFATU, CPYPAGT…)
│   ├── SRC/COBOL/                ← 10 programas COBOL
│   ├── JCL/                      ← LCSETUP1, LCDIA01, LCIMP01
│   ├── SQL/schema_v2.sql         ← 23 tabelas + seeds + índices
│   ├── RUNBOOK/ABEND-CATALOG.md  ← S0C7, S0C4, S322, S806, SQLCODE
│   ├── SCRIPTS/                  ← compile.sh, run-cycle.sh, setup-db.sh
│   ├── TESTDATA/                 ← arquivos de teste com falhas injetadas
│   ├── DOCS.md                   ← documentação técnica completa
│   └── integration-layer/        ← FastAPI v2.1.0 (Python 3.12)
│       ├── app/
│       │   ├── main.py           ← 22+ routers
│       │   ├── api/              ← cadastros, emissão, sinistro, corretagem…
│       │   ├── services/         ← motor de críticas, movimentação, batch
│       │   ├── ai/               ← RAG, agentes, MCP, guardrails
│       │   └── auth/             ← JWT + bcrypt
│       └── tests/                ← 252 testes (100 % passando)
```

---

## Produtos Suportados

| Produto | Descrição | Tipos de Capital |
|---------|-----------|------------------|
| **VGC** | Vida em Grupo Coletivo | Fixo (F) · Escalonado (E) · Múltiplo salarial (M) · Por faixa (B) · Por perfil (P) |
| **GLB** | Global Life Benefits | Mesmos tipos + cláusulas especiais |

---

## Ciclo Batch Diário

```
RECEBE ARQUIVO → SORT → VALIDA (ARQVAL01) → CARGA DB2
    → FATURA (FATURA01) → BAIXA (PAGTO01)
    → CONCILIA (CONCIL01) → COMISSÕES (COMIS01)
    → CLEARING (CLEAR01) → LIQUIDAÇÃO (SETTLE01)
    → DISPUTAS (DISPUT01) → EXTRATOS
```

---

## Como Rodar Localmente

### Pré-requisitos
- Python 3.12+
- GnuCOBOL 3.x
- PostgreSQL 15+

### Integration Layer

```bash
cd LifeCore-Mainframe/integration-layer
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
# Swagger: http://localhost:8000/docs
# Portal do Corretor: http://localhost:8000/portal
```

### COBOL (compilação local)

```bash
cd LifeCore-Mainframe
chmod +x SCRIPTS/compile.sh
./SCRIPTS/compile.sh
```

### Testes

```bash
cd LifeCore-Mainframe/integration-layer
pytest tests/ --ignore=tests/e2e -q
# 252 passed
```

---

## Estratégia de Branches

```
main
 └── develop
      ├── feat/{agente}/LCIQ-###-descricao
      ├── fix/{agente}/LCIQ-###-descricao
      ├── chore/{agente}/LCIQ-###-descricao
      ├── spike/{agente}/LCIQ-###-descricao
      ├── hotfix/{agente}/LCIQ-###-descricao
      └── release/YYYY.QN
```

**Slugs dos agentes:** `fat` · `ren` · `sus` · `mlc` · `prd` · `seg` · `cor` · `com` · `sin` · `cnc` · `arq` · `int` · `qdt` · `bia` · `gov` · `qat` · `rag` · `orc`

Todo commit deve referenciar a issue Jira: `git commit -m "LCIQ-042: descrição"`

---

## Jira

- **Projeto:** `LifeCore IQ` · Chave `LCIQ`
- **Tipo:** Scrum · Sprint de 2 semanas
- **Agentes:** 18 (ver `AGENTS.md`)
- **Automação:** branch criada → issue move para *Em Desenvolvimento*; PR merged → *Validação QA*

---

## Regulatório

- **SUSEP** — seguros de vida em grupo
- **LGPD** — dados pessoais mascarados; CPF/PAN nunca armazenados em claro
- **PCI-DSS** — token + 4 últimos dígitos do cartão; PAN nunca persistido
- **Banco Central** — clearing, liquidação e conciliação de pagamentos

---

## Licença

Projeto educacional / portfólio. Conformidade regulatória formal exige validação jurídica.
