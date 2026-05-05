# M02 — Estrutura do Projeto Python

> **Tipo:** Tarefa Claude Code
> **Tempo estimado:** 1-1.5h
> **Dependências:** M01 concluído
> **Próximo módulo:** M03 (já está pronto, é este CLAUDE.md) ou M04 (configuração e settings)

---

## Como usar este documento

Este arquivo contém **o prompt completo** para você colar no Claude Code (ou Claude.ai/Cursor/etc) e produzir o código deste módulo.

Antes de colar:
1. Garanta que `CLAUDE.md` está na raiz do repositório
2. Garanta que `docs/taxonomia.md` e `docs/kpis.md` estão em `docs/`
3. Inicialize um repositório Git vazio: `git init`
4. Crie um remoto (GitHub/Azure DevOps) e linke
5. Faça o primeiro commit dos arquivos de documentação acima

Depois cole o prompt abaixo no Claude Code.

---

## Prompt para Claude Code

```
# Contexto

Você está trabalhando no projeto email-intelligence. Antes de começar:

1. LEIA o arquivo CLAUDE.md na raiz do projeto (é o documento de contexto principal)
2. LEIA docs/taxonomia.md e docs/kpis.md (definições de domínio)

Estamos no módulo M02 — Estrutura do Projeto Python.

Os módulos M01 (provisionamento Azure) já foi concluído manualmente. O próximo
após este será M04 (configuração e settings).

# Tarefa

Criar a estrutura inicial do projeto Python, seguindo as convenções definidas
em CLAUDE.md (seção 4 — Convenções de Código).

## Entregáveis

### 1. pyproject.toml

Crie pyproject.toml com:

- Build system: setuptools (não poetry, não uv build — manter simples)
- Python 3.11+
- Dependências runtime divididas em grupos lógicos:

  Core:
    - pydantic>=2.6
    - pydantic-settings>=2.2
    - sqlalchemy[asyncio]>=2.0
    - asyncpg>=0.29
    - alembic>=1.13
    - python-dotenv>=1.0

  Microsoft / Azure:
    - msgraph-sdk>=1.0
    - azure-identity>=1.15
    - azure-keyvault-secrets>=4.7
    - azure-keyvault-certificates>=4.7
    - azure-storage-blob>=12.19

  AI:
    - openai>=1.30
    - tiktoken>=0.6

  Email processing:
    - beautifulsoup4>=4.12
    - lxml>=5.1
    - talon (versão mais recente disponível)

  Streamlit / Web:
    - streamlit>=1.32
    - msal>=1.27
    - msal-streamlit-authenticator (ou implementação custom se não existir)
    - plotly>=5.20
    - pandas>=2.2

  Salesforce:
    - simple-salesforce>=1.12

  Utilitários:
    - structlog>=24.1
    - tenacity>=8.2

- Dependências dev:
    - pytest>=8.0
    - pytest-asyncio>=0.23
    - pytest-cov>=4.1
    - ruff>=0.3
    - mypy>=1.9
    - types-beautifulsoup4
    - aioresponses (mock de aiohttp)
    - pytest-postgresql (ou testcontainers-python como alternativa)

- Configuração ruff:
  - line-length: 100
  - target-version: py311
  - select: ["E", "W", "F", "I", "N", "B", "UP", "S", "A", "C4", "DTZ", "T20", "PT", "RET", "SIM", "ARG", "PL"]
  - ignore: ["E501", "PLR0913"]
  - per-file-ignores: tests/* podem ignorar S101 (assert)

- Configuração mypy:
  - strict = true
  - python_version = "3.11"
  - warn_return_any = true
  - disallow_untyped_defs = true
  - exclude para alembic/versions e tests

- Configuração pytest:
  - asyncio_mode = "auto"
  - testpaths = ["tests"]
  - addopts: -v --tb=short --strict-markers

### 2. Estrutura de pastas

Criar TODAS as pastas listadas em CLAUDE.md seção 4 (estrutura de pastas), com
arquivos `__init__.py` em cada diretório de código:

src/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py            # placeholder, será implementado em M04
│   └── logging.py             # placeholder, será implementado em M04
├── domain/
│   ├── __init__.py
│   ├── email.py               # placeholder
│   ├── client.py              # placeholder
│   ├── classification.py      # placeholder
│   └── metrics.py             # placeholder
├── infrastructure/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── repositories/
│   │       └── __init__.py
│   ├── graph_client/
│   │   └── __init__.py
│   ├── openai_client/
│   │   └── __init__.py
│   ├── blob_storage/
│   │   └── __init__.py
│   ├── salesforce_client/
│   │   └── __init__.py
│   └── key_vault/
│       └── __init__.py
├── services/
│   ├── __init__.py
│   ├── ingestion/
│   │   └── __init__.py
│   ├── classification/
│   │   └── __init__.py
│   ├── client_resolution/
│   │   └── __init__.py
│   ├── metrics/
│   │   └── __init__.py
│   └── audit/
│       └── __init__.py
├── jobs/
│   └── __init__.py
├── admin_panel/
│   ├── __init__.py
│   ├── pages/
│   │   └── __init__.py
│   └── components/
│       └── __init__.py
└── shared/
    ├── __init__.py
    ├── exceptions.py          # já implementar (ver abaixo)
    ├── constants.py           # já implementar (ver abaixo)
    └── utils.py               # placeholder

tests/
├── __init__.py
├── conftest.py                # placeholder mínimo
├── unit/
│   └── __init__.py
├── integration/
│   └── __init__.py
└── fixtures/
    └── __init__.py

alembic/
└── (vazio por enquanto, será inicializado em M05)

scripts/
└── (vazio)

docs/
└── (já tem conteúdo de M03)

prompts_claude_code/
└── (já tem M01 e M02)

infra/
└── (vazio, futuro Bicep/Terraform)

### 3. Implementar src/shared/exceptions.py

Crie a hierarquia base de exceções customizadas do projeto:

```python
"""Custom exceptions for the email-intelligence platform."""


class EmailIntelligenceError(Exception):
    """Base exception for all custom errors in this project."""


class ConfigurationError(EmailIntelligenceError):
    """Raised when configuration is invalid or missing."""


class GraphAPIError(EmailIntelligenceError):
    """Raised when Microsoft Graph API returns an error."""


class GraphRateLimitError(GraphAPIError):
    """Raised when Graph API returns 429 (rate limited)."""


class GraphAuthenticationError(GraphAPIError):
    """Raised when Graph authentication fails."""


class GraphPermissionError(GraphAPIError):
    """Raised when Graph denies access to a mailbox."""


class OpenAIError(EmailIntelligenceError):
    """Raised when Azure OpenAI returns an error."""


class ClassificationError(EmailIntelligenceError):
    """Raised when email classification fails."""


class InvalidClassificationOutputError(ClassificationError):
    """Raised when LLM returns invalid JSON output."""


class IngestionError(EmailIntelligenceError):
    """Raised during email ingestion pipeline."""


class ContentCleaningError(EmailIntelligenceError):
    """Raised during email content preprocessing."""


class ClientResolutionError(EmailIntelligenceError):
    """Raised when client resolution fails for an email."""


class MetricsCalculationError(EmailIntelligenceError):
    """Raised during metrics calculation."""


class ImmutableStateError(EmailIntelligenceError):
    """Raised when an attempted operation would violate read-only invariants
    (e.g. trying to modify a mailbox via Graph)."""


class AuditLogError(EmailIntelligenceError):
    """Raised when audit logging fails (should NEVER silence)."""
```

### 4. Implementar src/shared/constants.py

```python
"""Project-wide constants."""

from typing import Final

# === Email classification ===

DIRECTION_INBOUND: Final[str] = "INBOUND"
DIRECTION_OUTBOUND_REACTIVE: Final[str] = "OUTBOUND_REACTIVE"
DIRECTION_OUTBOUND_PROACTIVE: Final[str] = "OUTBOUND_PROACTIVE"
DIRECTION_INTERNAL: Final[str] = "INTERNAL"
DIRECTION_OTHER: Final[str] = "OTHER"

ALL_DIRECTIONS: Final[tuple[str, ...]] = (
    DIRECTION_INBOUND,
    DIRECTION_OUTBOUND_REACTIVE,
    DIRECTION_OUTBOUND_PROACTIVE,
    DIRECTION_INTERNAL,
    DIRECTION_OTHER,
)

PROACTIVE_CONTRACTED: Final[str] = "PROACTIVE_CONTRACTED"
PROACTIVE_OPPORTUNITY: Final[str] = "PROACTIVE_OPPORTUNITY"
PROACTIVE_RELATIONSHIP: Final[str] = "PROACTIVE_RELATIONSHIP"
PROACTIVE_OPERATIONAL: Final[str] = "PROACTIVE_OPERATIONAL"
PROACTIVE_OTHER: Final[str] = "PROACTIVE_OTHER"

ALL_PROACTIVE_SUBCATEGORIES: Final[tuple[str, ...]] = (
    PROACTIVE_CONTRACTED,
    PROACTIVE_OPPORTUNITY,
    PROACTIVE_RELATIONSHIP,
    PROACTIVE_OPERATIONAL,
    PROACTIVE_OTHER,
)

THREAD_INITIATED_US: Final[str] = "THREAD_INITIATED_US"
THREAD_INITIATED_CLIENT: Final[str] = "THREAD_INITIATED_CLIENT"
THREAD_INITIATED_UNCLEAR: Final[str] = "THREAD_INITIATED_UNCLEAR"

# === RBAC roles ===

ROLE_ADMIN: Final[str] = "ADMIN"
ROLE_PORTFOLIO_MANAGER: Final[str] = "PORTFOLIO_MANAGER"
ROLE_VIEWER: Final[str] = "VIEWER"

# === Client status ===

CLIENT_STATUS_ACTIVE: Final[str] = "ACTIVE"
CLIENT_STATUS_PROSPECT: Final[str] = "PROSPECT"
CLIENT_STATUS_INACTIVE: Final[str] = "INACTIVE"

# === Body truncation ===

BODY_CLEAN_MAX_CHARS: Final[int] = 4000

# === Confidence thresholds ===

CONFIDENCE_ESCALATION_THRESHOLD: Final[float] = 0.7
CONFIDENCE_OTHER_FALLBACK_THRESHOLD: Final[float] = 0.5

# === Calibration thresholds ===

TARGET_AGREEMENT_LEVEL_A: Final[float] = 0.85
TARGET_AGREEMENT_LEVEL_C: Final[float] = 0.75

# === Time windows ===

PROACTIVE_RESPONSE_WINDOW_DAYS: Final[int] = 7
ABANDONED_CLIENT_WINDOW_DAYS: Final[int] = 30
MISSING_MANAGER_WINDOW_DAYS: Final[int] = 7

# === Models ===

DEFAULT_CLASSIFICATION_MODEL: Final[str] = "gpt-4o-mini"
ESCALATION_CLASSIFICATION_MODEL: Final[str] = "gpt-4o"
EMBEDDING_MODEL: Final[str] = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: Final[int] = 1536
```

### 5. .gitignore

Crie um .gitignore Python completo, incluindo:

- Python: __pycache__, *.pyc, *.pyo, .pytest_cache, .coverage, htmlcov/, .mypy_cache, .ruff_cache
- Virtual envs: venv/, .venv/, env/, ENV/
- IDE: .idea/, .vscode/ (exceto launch.json e settings.json se quiser commitar), *.swp, *.swo
- OS: .DS_Store, Thumbs.db
- Env vars: .env, .env.local, .env.*.local
- Secrets: *.pfx, *.cer, *.key, *.pem (TODOS — nunca commitar certificados/chaves)
- Build: dist/, build/, *.egg-info/
- Azure: .azure/, local.settings.json (Azure Functions)
- Streamlit: .streamlit/secrets.toml
- Logs: *.log, logs/
- Data local: data/, *.db, *.sqlite, *.sqlite3
- Temp: tmp/, temp/, .cache/
- Alembic: alembic/versions/__pycache__/

### 6. .env.example

Lista de TODAS as variáveis de ambiente que o sistema usa, com valores
ilustrativos e comentários:

```
# === Environment ===
ENVIRONMENT=development  # development | production

# === Logging ===
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR

# === Azure Identity ===
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_CERT_THUMBPRINT=ABCDEF1234567890ABCDEF1234567890ABCDEF12

# === Azure Key Vault ===
AZURE_KEY_VAULT_URL=https://kv-email-intel-prod.vault.azure.net/
AZURE_CERT_KEY_VAULT_NAME=email-intel-cert

# === Azure OpenAI ===
# These are read from Key Vault in production. Only set here for local dev.
AZURE_OPENAI_ENDPOINT=https://your-aoai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI=gpt-4o-mini
AZURE_OPENAI_DEPLOYMENT_GPT4O=gpt-4o
AZURE_OPENAI_DEPLOYMENT_EMBEDDINGS=text-embedding-3-small

# === Postgres ===
# In production, read from Key Vault. For local dev, set explicitly.
POSTGRES_CONNECTION_STRING=postgresql+asyncpg://pgadmin:password@pg-email-intel-prod.postgres.database.azure.com:5432/email_intel?ssl=require

# === Storage ===
AZURE_STORAGE_ACCOUNT_NAME=stemailintelprod
AZURE_STORAGE_CONTAINER_EMAILS_RAW=emails-raw
AZURE_STORAGE_CONTAINER_PROMPTS=prompts-archive
AZURE_STORAGE_CONTAINER_EXPORTS=exports

# === Internal email domains (comma-separated) ===
INTERNAL_EMAIL_DOMAINS=simpleenergy.com.br

# === Application Insights ===
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...

# === Salesforce (será preenchido em M26) ===
SALESFORCE_USERNAME=
SALESFORCE_PASSWORD=
SALESFORCE_TOKEN=
SALESFORCE_DOMAIN=login

# === Streamlit / Admin Panel ===
ADMIN_PANEL_BASE_URL=https://app-email-intel-prod.azurewebsites.net
INITIAL_ADMIN_EMAILS=rodrigo.reis@simpleenergy.com.br,sadraque.paiva@simpleenergy.com.br
```

### 7. README.md

Um README enxuto, em português, com:

- Visão geral do projeto (3-5 linhas)
- Stack principal (lista)
- Pré-requisitos para desenvolvimento local (Python 3.11+, Postgres opcional, Azure CLI logado)
- Setup local (clone, venv, install, .env)
- Como rodar:
  - Job semanal: `python -m src.jobs.weekly_batch`
  - Painel admin: `streamlit run src/admin_panel/app.py`
  - Testes: `pytest`
  - Lint: `ruff check .`
  - Type check: `mypy src/`
- Link para CLAUDE.md como fonte de verdade
- Link para docs/

Mantenha enxuto. Quem quer detalhe vai pra docs/.

### 8. tests/conftest.py

Placeholder mínimo:

```python
"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests run in test environment."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
```

### 9. Pre-commit hooks (opcional mas recomendado)

Crie .pre-commit-config.yaml com:
  - ruff (lint + format)
  - mypy
  - check-added-large-files
  - check-merge-conflict
  - end-of-file-fixer
  - trailing-whitespace

Não é mandatório instalar, mas o arquivo deve estar presente.

### 10. Makefile (opcional, mas conveniente)

Targets úteis:
- install: pip install -e ".[dev]"
- lint: ruff check .
- format: ruff format .
- typecheck: mypy src/
- test: pytest
- test-cov: pytest --cov=src --cov-report=term-missing
- check: lint + typecheck + test (rodar em sequência, falhar no primeiro erro)
- run-job: python -m src.jobs.weekly_batch
- run-panel: streamlit run src/admin_panel/app.py

# Critério de aceite

- [ ] pyproject.toml válido (`pip install -e ".[dev]"` funciona)
- [ ] Todas as pastas e __init__.py criados conforme estrutura
- [ ] src/shared/exceptions.py implementado completo
- [ ] src/shared/constants.py implementado completo
- [ ] .gitignore cobrindo Python, IDEs, secrets, OS
- [ ] .env.example com TODAS as variáveis listadas
- [ ] README.md em português, conciso
- [ ] tests/conftest.py funcional (mesmo que vazio de testes reais)
- [ ] `ruff check .` passa sem erros
- [ ] `mypy src/` passa sem erros (mesmo com módulos quase vazios)
- [ ] Não há código TODO sem justificativa — placeholders devem ter comentário
  "# Will be implemented in M{NN}"

# Restrições

- NÃO implemente settings.py, logging.py ou models.py — esses são M04 e M05
- Mantenha placeholders com comentário indicando módulo futuro
- NÃO commite arquivos .env, .pfx, .cer, .key — devem estar no .gitignore
- Use exatamente a estrutura de pastas de CLAUDE.md seção 4
- Siga exatamente os princípios de naming de CLAUDE.md seção 4

# Entregáveis (checklist)

- [ ] pyproject.toml
- [ ] .gitignore
- [ ] .env.example
- [ ] README.md
- [ ] Makefile
- [ ] .pre-commit-config.yaml
- [ ] src/ com toda a árvore de pastas e __init__.py
- [ ] src/shared/exceptions.py implementado
- [ ] src/shared/constants.py implementado
- [ ] tests/conftest.py implementado
- [ ] Estrutura de tests/ criada

# Após concluir

- Atualize CLAUDE.md, seção 8 ("Estado Atual do Projeto"):
  - Módulos concluídos: M01, M02
  - Próximo módulo: M04
- Faça commit com mensagem: "feat(M02): initial project structure with conventions"
```

---

## Verificação após Claude Code terminar

Antes de marcar M02 como concluído, rode na raiz do projeto:

```bash
# Setup virtual env
python3.11 -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows

# Install
pip install -e ".[dev]"

# Lint
ruff check .

# Type check (vai dar warnings em placeholders, OK)
mypy src/

# Test (não há testes ainda, deve sair limpo)
pytest

# Verificar estrutura
tree src/ -L 3 --dirsfirst
```

Se tudo passa, M02 está concluído. Commitar e seguir para M04.

---

## Notas

- Mesmo que algumas dependências em `pyproject.toml` não sejam usadas
  imediatamente, declarar agora evita conflitos de versão depois
- O `talon` pode ser substituído por implementação custom em M13 se houver
  problemas de compatibilidade no Linux/Azure Functions — observar
- `msal-streamlit-authenticator` pode não existir publicamente — se for o
  caso, instruir Claude Code a usar `msal` puro com session_state do Streamlit
- Esta versão usa `setuptools` build backend por simplicidade; se preferir
  `hatchling` ou `uv`, ajustar conforme

---

## Próximo passo

Após concluir M02:
- Iniciar **M04 — Configuração e Settings** (próximo prompt a ser produzido)
- M03 (CLAUDE.md) já está pronto e em uso
