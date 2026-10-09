# Setup — Ambiente de Desenvolvimento LifeCore IQ

## Pré-requisitos

| Ferramenta | Versão mínima | Instalação |
|------------|--------------|------------|
| Python | 3.12+ | `pyenv install 3.12.5` |
| GnuCOBOL | 3.x | `sudo dnf install gnucobol` |
| PostgreSQL | 15+ | `sudo dnf install postgresql-server` |
| Git | 2.40+ | já instalado |

## 1. Clonar e configurar

```bash
git clone https://github.com/Romilsonlonan/lifecore-cobol.git
cd lifecore-cobol
```

## 2. Integration Layer

```bash
cd LifeCore-Mainframe/integration-layer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite .env com suas credenciais de banco
uvicorn app.main:app --reload --port 8000
```

## 3. Banco de dados

```bash
cd LifeCore-Mainframe
./SCRIPTS/setup-db.sh
# cria schema_v2 no PostgreSQL local
```

## 4. COBOL (compilação local com GnuCOBOL)

```bash
cd LifeCore-Mainframe
./SCRIPTS/compile.sh
# compila todos os programas em SRC/COBOL/
```

## 5. Testes

```bash
cd LifeCore-Mainframe/integration-layer
pytest tests/ --ignore=tests/e2e -q
# esperado: 252 passed
```

## 5.1 Pre-commit e segurança (obrigatório)

```bash
# Instalar hooks no repositório (uma vez após clonar)
pip install pre-commit detect-secrets bandit presidio-analyzer presidio-anonymizer
pre-commit install

# Gerar baseline de segredos existentes (uma vez)
python3 -m detect_secrets scan \
  --exclude-files '.*\.lock$' --exclude-files '.*\.svg$' \
  > .secrets.baseline

# Executar todos os hooks manualmente
pre-commit run --all-files
```

**Variáveis extras para o módulo de fraude:**
```env
FRAUD_API_PROVIDER=mock        # mock | watsonx | openai
FRAUD_API_KEY=                 # necessário para watsonx/openai
FRAUD_API_URL=                 # necessário para watsonx
```

## 6. Portal do Corretor

Após subir a Integration Layer, acesse:
```
http://localhost:8000/portal
```

## 7. Swagger / OpenAPI

```
http://localhost:8000/docs
```

## Variáveis de ambiente (.env)

```
DATABASE_URL=postgresql://lifecore:senha@localhost:5432/lifecore_iq
JWT_SECRET_KEY=troque-em-producao
OTEL_ENABLED=false
RECEITA_WS_ENABLED=false

# Módulo de fraude atuarial (LCIQ-3)
FRAUD_API_PROVIDER=mock        # mock | watsonx | openai
FRAUD_API_KEY=
FRAUD_API_URL=
```

## Convenção de branches

```
feat/{agente}/LCIQ-###-descricao   # nova funcionalidade
fix/{agente}/LCIQ-###-descricao    # correção de bug
chore/{agente}/LCIQ-###-descricao  # infra / configuração
docs/{agente}/LCIQ-###-descricao   # documentação
hotfix/{agente}/LCIQ-###-descricao # correção urgente em produção
```

## Referência dos agentes

Ver `AGENTS.md` na raiz do repositório.
