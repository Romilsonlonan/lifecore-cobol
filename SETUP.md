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
