# CLAUDE.md — Contexto Principal do Projeto

> **Este documento é a fonte de verdade para o Claude Code.** Antes de qualquer tarefa neste projeto, leia este arquivo. Se houver conflito entre uma instrução pontual e este documento, pergunte antes de prosseguir.

---

## 1. Sobre o Projeto

**Nome:** email-intelligence
**Empresa:** Simple Energy (Brasil)
**Tipo:** Plataforma corporativa de inteligência de comunicação por e-mail

### Objetivo de negócio

Responder, com dados quantitativos e periódicos, à seguinte pergunta da diretoria:

> "Estamos sendo proativos demais com clientes que não pediram nada, ou estamos sendo apenas reativos? Onde está o esforço da equipe comercial sendo investido?"

A plataforma lê e-mails das caixas autorizadas via Microsoft Graph, classifica cada mensagem com IA (Azure OpenAI), e gera dashboards e KPIs que medem o **balanço entre comunicação proativa e reativa** com clientes.

### Pergunta de negócio principal

A métrica-chefe do projeto é o **Índice de Esforço Não-Solicitado**:
> % de e-mails enviados aos clientes que são proativos não-contratados, em threads iniciadas por nós, sem resposta do cliente em 7 dias.

Tudo o que construímos serve, em primeiro lugar, para responder bem a essa métrica.

---

## 2. Arquitetura — Visão Resumida

```
Microsoft 365 / Exchange Online (origem)
        │
        ▼ (Microsoft Graph API, certificate auth)
[Azure Function — Job Semanal] ──► [Postgres + pgvector]
        │                                  │
        ├──► [Azure Blob — JSON cru]      │
        │                                  │
        ▼                                  ▼
[Azure OpenAI Service]              [App Service — Streamlit]
  - GPT-4o-mini (classificação)            - Painel Admin
  - GPT-4o (escalada)                      - Dashboards
  - text-embedding-3-small                 - Calibração da IA
```

**Stack:**

- **Cloud:** Azure (Brazil South)
- **Linguagem principal:** Python 3.11+
- **Banco operacional:** Postgres Flexible Server B1ms + pgvector
- **Storage de e-mails crus:** Azure Blob Storage (JSON por e-mail)
- **IA:** Azure OpenAI Service (não OpenAI direta)
- **Identidade da app:** Entra ID App Registration + Application Access Policy
- **Painel admin:** Streamlit + SSO Entra ID
- **Job batch:** Azure Function (timer trigger semanal)
- **Auth do painel:** SSO via Entra ID (msal-streamlit)
- **Secrets:** Azure Key Vault
- **Observabilidade:** Application Insights + tabela `audit_log`

**Frequência de processamento:** batch semanal (toda segunda-feira 6h, fuso America/Sao_Paulo).

---

## 3. Princípios Arquiteturais Inviolaveis

Estes princípios não podem ser violados em nenhuma circunstância. Se uma tarefa parecer exigir violação, pergunte antes.

### 3.1 Read-Only no Microsoft Graph

O sistema é **estritamente read-only** sobre as caixas de e-mail dos usuários, com **uma única exceção** documentada abaixo.

**Implicações práticas:**

- Nunca usar verbos HTTP `PATCH`, `POST`, `DELETE` ou `PUT` em endpoints `/me/messages/*`, `/users/{id}/messages/*`, `/users/{id}/mailFolders/*`
- Nunca chamar `GET /messages/{id}` em mensagem individual sem antes capturar o estado `isRead` original
- Nunca mover, marcar, sinalizar, categorizar ou modificar e-mails
- Listagem com `$select` é o método padrão (não marca como lido)

**Única exceção permitida:**

Restauração de `isRead` para o estado original quando, por qualquer motivo, uma chamada acidentalmente marcar uma mensagem como lida. O fluxo é:

1. Capturar `isRead` original na listagem
2. Processar
3. Se `isRead` mudou e não devia: `PATCH /messages/{id}` com `{"isRead": false}` para restaurar

Esta exceção deve ser implementada como salvaguarda automática em `graph_client`, com logging dedicado.

### 3.2 Idempotência

Todos os jobs e pipelines devem ser **idempotentes**: re-executar uma tarefa não deve gerar duplicações nem efeitos colaterais.

- Ingestão usa `UPSERT` baseado em `UNIQUE(mailbox_id, graph_message_id)`
- Classificações são versionadas por `prompt_version`
- Embeddings têm `source_text_hash` para evitar re-processamento
- Métricas semanais sobrescrevem o snapshot da semana

### 3.3 Soft Delete

Nunca DELETE físico em tabelas críticas (caixas, clientes, classificações, e-mails). Use `deleted_at TIMESTAMP NULL` + filtros padrão.

### 3.4 Sem Credenciais em Código

- Toda credencial vem de Azure Key Vault (em produção) ou `.env` (em dev)
- Settings centralizados em `src/config/settings.py` (Pydantic Settings)
- Nunca usar `os.getenv()` direto fora do módulo de settings
- Certificate-based auth para Microsoft Graph (nunca client secret)

### 3.5 Logs Estruturados

Todo log em formato JSON com campos mínimos: `timestamp`, `level`, `message`, `correlation_id`, `mailbox_id` (se aplicável), `run_id` (se aplicável).

### 3.6 Type Hints Obrigatórios

`mypy --strict` deve passar sem erros em todo código novo.

### 3.7 Migrations Versionadas

Toda alteração de schema via Alembic. Nunca alterar o banco diretamente.

### 3.8 Domínio Puro

A camada `src/domain/` não pode importar de `src/infrastructure/` nem de bibliotecas externas (exceto stdlib e Pydantic). Domínio define entidades e regras de negócio puras.

---

## 4. Convenções de Código

### Idioma

- **Código (variáveis, classes, funções, comentários técnicos):** inglês
- **Banco de dados (tabelas, colunas):** inglês
- **Conteúdo de domínio armazenado (descrições, nomes):** português
- **Documentação (`docs/`, READMEs):** português
- **Mensagens da UI (Streamlit):** português
- **Logs:** inglês (mais fácil para troubleshoot técnico)

### Naming

- Tabelas: `snake_case`, plural (`monitored_mailboxes`, `email_messages`)
- Colunas: `snake_case`, singular (`mailbox_id`, `received_at`)
- Classes Python: `PascalCase` (`MailboxIngester`)
- Funções/variáveis Python: `snake_case` (`ingest_messages`)
- Constantes: `UPPER_SNAKE_CASE` (`MAX_RETRIES`)
- Arquivos Python: `snake_case.py`
- Enums em DB: armazenar como string (`PROACTIVE_CONTRACTED`)
- IDs internos: UUID v4
- IDs externos (Graph, Salesforce): em colunas separadas com prefixo (`graph_user_id`, `sf_account_id`)

### Datas e fusos

- **Tudo em UTC no banco** (timestamps com timezone)
- Conversão para `America/Sao_Paulo` apenas na apresentação (Streamlit)
- Sempre usar `datetime.now(timezone.utc)`, nunca `datetime.utcnow()`
- Coluna `created_at` e `updated_at` em todas as tabelas

### Async vs Sync

- Padrão: **async** em toda I/O (Graph, OpenAI, Postgres via SQLAlchemy 2.0 async)
- Streamlit é sync por natureza — usar `asyncio.run()` na borda quando necessário
- Não misturar sync e async dentro do mesmo módulo de service

### Estrutura de pastas

```
src/
├── config/                   # Settings, logging
├── domain/                   # Entidades puras, sem dependências externas
├── infrastructure/           # Adapters: DB, Graph, OpenAI, Blob, Salesforce
│   ├── database/
│   │   ├── models.py        # SQLAlchemy
│   │   ├── session.py
│   │   └── repositories/
│   ├── graph_client/
│   ├── openai_client/
│   ├── blob_storage/
│   ├── salesforce_client/
│   └── key_vault/
├── services/                 # Casos de uso de negócio
│   ├── ingestion/
│   ├── classification/
│   ├── client_resolution/
│   ├── metrics/
│   └── audit/
├── jobs/                     # Entry points dos jobs batch
│   ├── weekly_batch.py
│   ├── recalibration.py
│   └── salesforce_sync.py
├── admin_panel/              # Streamlit
│   ├── app.py
│   ├── auth.py
│   ├── pages/
│   └── components/
└── shared/                   # Exceções, utils, constantes
```

---

## 5. Glossário de Domínio

| Termo | Definição |
|-------|-----------|
| **Caixa** | Mailbox individual de um usuário do M365 (ex: maria@simpleenergy.com.br) |
| **Caixa Monitorada** | Caixa que foi autorizada e cadastrada no sistema |
| **Carteira** | Grupo de clientes sob responsabilidade de um gerente comercial |
| **Cliente / Conta** | Empresa cliente (ex: ACME Ltda) |
| **Contato** | Pessoa específica de um cliente (ex: joao@acme.com) |
| **Thread** | Conversa de e-mail (agrupada por `conversationId` do Graph) |
| **Comunicação Contratada** | Envio periódico esperado a um cliente (relatório, NF, cobrança) |
| **Inbound** | E-mail recebido de cliente externo |
| **Outbound** | E-mail enviado a cliente externo |
| **Internal** | E-mail interno (entre membros da empresa) |
| **Outbound Proactive** | Envio nosso sem ter sido provocado por mensagem anterior |
| **Outbound Reactive** | Envio nosso em resposta a algo (e-mail, ligação, reunião) |
| **Reativo Offline** | Resposta a contato off-line (ligação, reunião, WhatsApp) |
| **Calibração** | Processo de revisão humana da classificação da IA |
| **Few-Shot** | Exemplos validados que entram no prompt para melhorar precisão |

Para definições completas da taxonomia, ver `docs/taxonomia.md`.

---

## 6. Decisões Arquiteturais Já Fechadas

Estas decisões foram tomadas na fase consultiva e **não devem ser revisitadas sem discussão explícita**:

1. **Azure OpenAI** (não OpenAI direta) — compliance e integração nativa com tenant
2. **Postgres único** + Blob para JSON cru — simplicidade operacional
3. **pgvector** (não vector DB dedicado) — escala compatível
4. **text-embedding-3-small** (1536 dim) — custo/qualidade adequado
5. **GPT-4o-mini** padrão + **GPT-4o** em escalada (confidence < 0.7)
6. **Application Permission + Application Access Policy** — granularidade no Exchange
7. **Certificate-based auth** (não client secret) — segurança superior
8. **Streamlit** para painel admin — velocidade de desenvolvimento no MVP
9. **Batch semanal** (não real-time) — latência aceitável, custos baixos
10. **Soft delete universal** em tabelas críticas
11. **Truncamento de body em 4.000 caracteres** mantendo o início
12. **Sumarização recursiva de threads >5 mensagens**
13. **Pipeline de pré-processamento** com talon (signature/citation removal) como módulo de primeira classe
14. **Versionamento de prompts** com tabela `prompts` + cópia em Blob

---

## 7. Princípios para o Claude Code

Quando uma tarefa for solicitada:

### Sempre

- Leia este arquivo (CLAUDE.md) e os documentos relevantes em `docs/` antes de implementar
- Pergunte se houver ambiguidade — não chute
- Escreva testes para o código novo no mesmo PR
- Atualize documentação quando alterar comportamento
- Use type hints em tudo (mypy strict deve passar)
- Use logs estruturados nas operações de I/O
- Faça commits pequenos com mensagens descritivas

### Nunca

- Modifique o estado de e-mails no Microsoft Graph (read-only inviolável)
- Use `os.getenv()` direto fora de `src/config/settings.py`
- Faça DELETE físico em tabelas críticas
- Importe de `src/infrastructure/` dentro de `src/domain/`
- Hardcode credenciais, mesmo em testes
- Faça rollback de migrations em produção sem ADR registrando o motivo

### Em caso de dúvida

Pergunte. A pergunta certa economiza horas de retrabalho.

---

## 8. Estado Atual do Projeto

> Atualize esta seção a cada módulo concluído. Última atualização: [data inicial — pré-M01]

**Fase atual:** Fase 0 — Provisionamento e Fundação

**Módulos concluídos:** nenhum

**Próximo módulo:** M01 — Provisionamento Azure manual

---

## 9. Documentos Relacionados

- `docs/arquitetura.md` — visão detalhada da arquitetura
- `docs/taxonomia.md` — definições de proativo/reativo (CRÍTICO)
- `docs/kpis.md` — definições matemáticas dos KPIs
- `docs/prompts/classification_v1.0.md` — prompt de classificação ativo
- `docs/runbooks/` — procedimentos operacionais
- `docs/adr/` — registros de decisões arquiteturais
- `prompts_claude_code/` — prompts prontos para cada módulo

---

## 10. Contato e Governança

**Admin Global do Sistema:** rodrigo.reis@simpleenergy.com.br
**Segundo Admin:** sadraque.paiva@simpleenergy.com.br

Toda decisão arquitetural ou de escopo passa pelo Admin Global.

---

*Última revisão deste documento: pré-M01 (fase consultiva concluída).*
