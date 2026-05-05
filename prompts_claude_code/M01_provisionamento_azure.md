# M01 — Provisionamento Azure Manual

> **Tipo:** Atividade manual (você executa, sem código)
> **Tempo estimado:** 4-6h
> **Pré-requisitos:** acesso de Owner/Contributor na subscription Azure, acesso de Global Admin no Entra ID, acesso de Exchange Admin no Microsoft 365
> **Próximo módulo:** M02 (estrutura do projeto Python)

---

## Objetivo

Provisionar todos os recursos Azure e configurar o Entra ID App Registration que serão usados pelo sistema. Ao final deste módulo, você terá:

- Resource Group criado
- Entra ID App Registration consentida com permissões corretas
- Certificate-based authentication configurada
- Postgres com pgvector habilitado
- Storage Account com containers
- Function App e App Service provisionados
- Key Vault com certificado e secrets armazenados
- Managed Identities configuradas

---

## Convenções de naming

Use estes nomes para consistência (todos em lowercase, sem acentos):

| Recurso | Nome |
|---------|------|
| Resource Group | `rg-email-intel-prod` |
| Subscription | (a sua subscription da empresa) |
| Região | `Brazil South` |
| Entra ID App | `email-intelligence-platform` |
| Key Vault | `kv-email-intel-prod` |
| Postgres Server | `pg-email-intel-prod` |
| Storage Account | `stemailintelprod` (sem hífens — restrição de nome) |
| Function App | `func-email-intel-prod` |
| App Service | `app-email-intel-prod` |
| App Service Plan | `asp-email-intel-prod` |
| Security Group | `sg-email-intel-monitored` |
| Application Insights | `appi-email-intel-prod` |

---

## ETAPA 1 — Resource Group

### Via Azure Portal

1. Portal Azure → "Resource groups" → "+ Create"
2. Subscription: (sua)
3. Name: `rg-email-intel-prod`
4. Region: `Brazil South`
5. Review + create → Create

### Via Azure CLI (alternativa)

```bash
az login
az account set --subscription "<sua-subscription-id>"
az group create --name rg-email-intel-prod --location brazilsouth
```

✅ **Critério de aceite:** Resource Group `rg-email-intel-prod` existe e está vazio.

---

## ETAPA 2 — Entra ID App Registration

### 2.1 — Criar App Registration

1. Portal Azure → "Microsoft Entra ID" → "App registrations" → "+ New registration"
2. Name: `email-intelligence-platform`
3. Supported account types: **Accounts in this organizational directory only (Single tenant)**
4. Redirect URI: deixar em branco
5. Register

### 2.2 — Anotar IDs

Após criação, copie e guarde com segurança:

- **Application (client) ID**: `_______________________________`
- **Directory (tenant) ID**: `_______________________________`

Você usará esses valores em `.env` e Key Vault.

### 2.3 — API Permissions

1. App Registration → "API permissions" → "+ Add a permission"
2. Microsoft APIs → **Microsoft Graph**
3. **Application permissions** (NÃO Delegated)
4. Adicionar:
   - `Mail.Read` (Read mail in all mailboxes)
   - `User.Read.All` (Read all users' full profiles)
   - `Group.Read.All` (Read all groups)
5. Após adicionar todas, clicar **"Grant admin consent for [tenant]"**
6. Confirmar — todas as permissões devem aparecer com status verde "Granted for [tenant]"

✅ **Verificação:** as 3 permissões aparecem com check verde "Granted for [seu tenant]".

### 2.4 — Certificate-based Authentication

#### 2.4.1 — Gerar certificado self-signed

**No PowerShell (Windows):**

```powershell
# Gerar certificado válido por 2 anos
$cert = New-SelfSignedCertificate `
  -Subject "CN=email-intelligence-platform" `
  -CertStoreLocation "cert:\CurrentUser\My" `
  -KeyExportPolicy Exportable `
  -KeySpec Signature `
  -KeyLength 2048 `
  -KeyAlgorithm RSA `
  -HashAlgorithm SHA256 `
  -NotAfter (Get-Date).AddYears(2)

# Anotar o thumbprint (copie!)
$cert.Thumbprint

# Exportar a chave pública (.cer) — vai pro Entra ID
Export-Certificate -Cert $cert -FilePath "$HOME\Desktop\email-intel-public.cer"

# Exportar a chave privada (.pfx) — vai pro Key Vault
$password = ConvertTo-SecureString -String "DEFINA_UMA_SENHA_FORTE" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath "$HOME\Desktop\email-intel-private.pfx" -Password $password
```

**No Linux/Mac (alternativa via openssl):**

```bash
# Gerar chave privada e certificado
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout email-intel-private.key \
  -out email-intel-public.cer \
  -days 730 \
  -subj "/CN=email-intelligence-platform"

# Criar PFX (com senha)
openssl pkcs12 -export \
  -in email-intel-public.cer \
  -inkey email-intel-private.key \
  -out email-intel-private.pfx \
  -passout pass:DEFINA_UMA_SENHA_FORTE

# Anotar o thumbprint
openssl x509 -in email-intel-public.cer -fingerprint -sha256 -noout
```

#### 2.4.2 — Upload do certificado público no Entra ID

1. App Registration → "Certificates & secrets" → "Certificates" → "+ Upload certificate"
2. Selecionar o arquivo `email-intel-public.cer`
3. Description: `email-intel-cert-2026`
4. Add

✅ **Verificação:** certificado aparece listado com thumbprint correto.

### 2.5 — Anotar para o `.env` (depois)

```
AZURE_TENANT_ID=<directory-tenant-id>
AZURE_CLIENT_ID=<application-client-id>
AZURE_CERT_THUMBPRINT=<thumbprint-do-certificado>
```

---

## ETAPA 3 — Key Vault

### 3.1 — Criar Key Vault

Portal → "Key vaults" → "+ Create":

- Subscription: (sua)
- Resource group: `rg-email-intel-prod`
- Key vault name: `kv-email-intel-prod`
- Region: `Brazil South`
- Pricing tier: Standard
- **Access configuration:** Azure role-based access control (RBAC)
- Soft-delete: enabled (default)
- Purge protection: enabled
- Networking: Public endpoint (vamos restringir depois)

Review + create → Create.

### 3.2 — Dar permissão a você

1. Key Vault → "Access control (IAM)" → "+ Add role assignment"
2. Role: **Key Vault Administrator**
3. Members: seu usuário
4. Review + assign

### 3.3 — Upload do certificado privado (PFX)

1. Key Vault → "Objects" → "Certificates" → "+ Generate/Import"
2. Method: **Import**
3. Certificate name: `email-intel-cert`
4. Upload do arquivo `email-intel-private.pfx`
5. Password: a senha que você definiu na geração
6. Create

✅ **Verificação:** certificado aparece em "Certificates" com status "Enabled".

### 3.4 — Secrets que entrarão depois

Estes serão preenchidos durante o desenvolvimento:

- `azure-openai-endpoint` (após criar Azure OpenAI)
- `azure-openai-api-key` (após criar Azure OpenAI)
- `postgres-connection-string` (após criar Postgres)
- `storage-connection-string` (após criar Storage)
- `salesforce-client-id`, `salesforce-client-secret` (M26)

Por enquanto, deixe vazio.

---

## ETAPA 4 — Postgres Flexible Server

### 4.1 — Criar servidor

Portal → "Azure Database for PostgreSQL flexible servers" → "+ Create":

- Subscription: (sua)
- Resource group: `rg-email-intel-prod`
- Server name: `pg-email-intel-prod`
- Region: `Brazil South`
- PostgreSQL version: **16**
- Workload type: **Development**
- Compute + storage: **Burstable, Standard_B1ms** (1 vCore, 2 GiB RAM, 32 GiB storage)
- High availability: **Disabled** (MVP)
- Authentication method: **PostgreSQL authentication only**
- Admin username: `pgadmin`
- Password: gere uma senha forte e salve no Key Vault como secret `postgres-admin-password`
- Networking: **Public access (allowed IP addresses)**
  - Add current client IP address: ✅
  - Allow public access from any Azure service within Azure to this server: ✅ (necessário para Function/App Service acessarem)

Review + create → Create.

### 4.2 — Habilitar pgvector

Após criação:

1. Postgres Server → "Server parameters"
2. Buscar: `azure.extensions`
3. Adicionar: `VECTOR` (e `UUID-OSSP` se ainda não estiver)
4. Save

### 4.3 — Criar database

Conectar via `psql` ou Azure Data Studio:

```sql
CREATE DATABASE email_intel;
\c email_intel
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verificar
SELECT * FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');
```

### 4.4 — Salvar connection string no Key Vault

```
postgresql://pgadmin:<password>@pg-email-intel-prod.postgres.database.azure.com:5432/email_intel?sslmode=require
```

Key Vault → Secrets → "+ Generate/Import":
- Name: `postgres-connection-string`
- Value: a string acima
- Create

✅ **Verificação:** consegue conectar ao banco e listar extensions `vector`, `uuid-ossp`.

---

## ETAPA 5 — Storage Account (Blob)

### 5.1 — Criar Storage Account

Portal → "Storage accounts" → "+ Create":

- Subscription: (sua)
- Resource group: `rg-email-intel-prod`
- Storage account name: `stemailintelprod`
- Region: `Brazil South`
- Performance: **Standard**
- Redundancy: **Locally-redundant storage (LRS)** (mais barato, suficiente para MVP)
- Advanced:
  - Require secure transfer: **Enabled**
  - Allow enabling anonymous access on individual containers: **Disabled**
  - Enable storage account key access: **Enabled** (vamos usar Managed Identity também, mas key como fallback)
  - Minimum TLS version: **1.2**
- Networking: Public endpoint
- Data protection: defaults (soft delete habilitado)

Review + create → Create.

### 5.2 — Criar containers

Storage Account → "Containers" → "+ Container":

Criar 3 containers:

1. **`emails-raw`** — Public access level: **Private (no anonymous access)**
2. **`prompts-archive`** — Public access level: **Private**
3. **`exports`** — Public access level: **Private** (para exports CSV/PDF da UI)

### 5.3 — Salvar connection string

Storage Account → "Access keys" → "Show" key1 connection string → copiar.

Key Vault → Secrets → "+ Generate/Import":
- Name: `storage-connection-string`
- Value: a connection string completa
- Create

✅ **Verificação:** os 3 containers aparecem em "Containers".

---

## ETAPA 6 — Application Insights

Portal → "Application Insights" → "+ Create":

- Subscription: (sua)
- Resource group: `rg-email-intel-prod`
- Name: `appi-email-intel-prod`
- Region: `Brazil South`
- Resource Mode: **Workspace-based**
- Log Analytics Workspace: criar novo `law-email-intel-prod`

Review + create → Create.

Após criação, copiar a **Connection String** e salvar no Key Vault como `appinsights-connection-string`.

---

## ETAPA 7 — Function App (job semanal)

### 7.1 — Criar Function App

Portal → "Function App" → "+ Create" → "Consumption":

- Subscription: (sua)
- Resource group: `rg-email-intel-prod`
- Function App name: `func-email-intel-prod`
- Runtime stack: **Python**
- Version: **3.11**
- Region: `Brazil South`
- Operating System: **Linux**
- Hosting plan: **Consumption (Serverless)**
- Storage account: usar `stemailintelprod` (mesmo)
- Application Insights: enable, vincular ao `appi-email-intel-prod`

Review + create → Create.

### 7.2 — Configurar Managed Identity

Function App → "Identity" → "System assigned" → Status: **On** → Save.

Anotar o Object ID (Principal ID) gerado.

### 7.3 — Dar permissões à Managed Identity

**No Key Vault:**
- Access control (IAM) → Add role assignment
- Role: **Key Vault Secrets User**
- Member: a Managed Identity da Function App
- Save

**No Storage Account:**
- Access control (IAM) → Add role assignment
- Role: **Storage Blob Data Contributor**
- Member: a Managed Identity da Function App
- Save

**No Postgres:** acesso será via connection string (do Key Vault) com user/password. Sem necessidade de role específico.

✅ **Verificação:** Function App tem Identity habilitada e roles atribuídos.

---

## ETAPA 8 — App Service (Streamlit)

### 8.1 — Criar App Service Plan

Portal → "App Service plans" → "+ Create":

- Resource group: `rg-email-intel-prod`
- Name: `asp-email-intel-prod`
- Operating System: **Linux**
- Region: `Brazil South`
- Pricing tier: **Basic B1**

Review + create → Create.

### 8.2 — Criar App Service

Portal → "App Services" → "+ Create" → "Web App":

- Resource group: `rg-email-intel-prod`
- Name: `app-email-intel-prod`
- Publish: **Code**
- Runtime stack: **Python 3.11**
- Operating System: **Linux**
- Region: `Brazil South`
- App Service Plan: `asp-email-intel-prod` (existente)

Review + create → Create.

### 8.3 — Configurar Managed Identity (igual à Function App)

App Service → "Identity" → "System assigned" → On → Save.

### 8.4 — Dar permissões iguais às da Function App

- Key Vault: **Key Vault Secrets User**
- Storage: **Storage Blob Data Contributor**

### 8.5 — Configurar SSO Entra ID (Easy Auth)

App Service → "Authentication" → "Add identity provider":

- Identity provider: **Microsoft**
- App registration type: **Pick an existing app registration in this directory**
- Existing app registration: criar uma SEPARADA do `email-intelligence-platform` (essa é só pra ler e-mails)
  - Crie uma nova: `email-intelligence-webapp` (Web platform, redirect URI: `https://app-email-intel-prod.azurewebsites.net/.auth/login/aad/callback`)
- Restrict access: **Require authentication**
- Unauthenticated requests: **HTTP 302 Redirect: recommended for websites**

Save.

✅ **Verificação:** ao acessar `https://app-email-intel-prod.azurewebsites.net`, é redirecionado para login Microsoft.

---

## ETAPA 9 — Configurar variáveis de ambiente

### 9.1 — Function App

Function App → "Configuration" → "+ New application setting":

| Nome | Valor |
|------|-------|
| `AZURE_KEY_VAULT_URL` | `https://kv-email-intel-prod.vault.azure.net/` |
| `AZURE_TENANT_ID` | (do passo 2.2) |
| `AZURE_CLIENT_ID` | (do passo 2.2) |
| `AZURE_CERT_KEY_VAULT_NAME` | `email-intel-cert` |
| `ENVIRONMENT` | `production` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (do passo 6) |
| `LOG_LEVEL` | `INFO` |

Save.

### 9.2 — App Service (mesmas variáveis)

Igual ao 9.1, no App Service.

---

## ETAPA 10 — Verificações finais

Antes de partir para M02, validar:

- [ ] Resource Group `rg-email-intel-prod` criado
- [ ] App Registration `email-intelligence-platform` com 3 permissões consentidas
- [ ] Certificado público no Entra ID, privado no Key Vault
- [ ] Postgres acessível, com `vector` e `uuid-ossp` habilitados, database `email_intel` criado
- [ ] Storage Account com 3 containers
- [ ] Application Insights vinculado
- [ ] Function App com Managed Identity e roles
- [ ] App Service com Managed Identity, roles e Easy Auth (SSO)
- [ ] Todos os secrets necessários no Key Vault
- [ ] Variáveis de ambiente configuradas em Function App e App Service

### Smoke test (opcional mas recomendado)

No seu computador local, com Python 3.11+:

```bash
pip install azure-identity azure-keyvault-secrets

python3 << 'EOF'
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Faz login interativo (az login deve ter sido feito antes)
credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://kv-email-intel-prod.vault.azure.net/",
    credential=credential
)

# Tenta listar secrets
for secret in client.list_properties_of_secrets():
    print(f"Secret encontrado: {secret.name}")

print("✅ Acesso ao Key Vault funcionando")
EOF
```

Se isso funcionar, sua configuração está OK.

---

## Estimativa de custos do que foi provisionado

| Recurso | Custo mensal estimado (USD) |
|---------|------------------------------|
| Postgres B1ms + 32GB | ~$25 |
| Storage Account (LRS, ~50GB) | ~$2 |
| Function App (Consumption) | ~$0-5 |
| App Service B1 | ~$13 |
| Key Vault | ~$1 |
| Application Insights (~5GB ingest) | ~$5 |
| **Total infra Azure** | **~$50/mês** |

(Não incluído: Azure OpenAI, que será adicionado em módulo posterior).

---

## Próximo passo

Após concluir M01 com todas as verificações:

1. Marcar M01 como concluído na seção 8 do `CLAUDE.md`
2. Iniciar **M02 — Estrutura do Projeto Python** (ver `prompts_claude_code/M02_estrutura_projeto.md`)

---

## Troubleshooting comum

### Erro: "User does not have permission to register applications"
Você precisa de role **Application Administrator** ou **Cloud Application Administrator** no Entra ID.

### Erro: "Cannot create resource - quota exceeded"
A subscription pode ter limite de recursos por região. Solicite aumento de quota ou tente outra região (mas mantenha tudo na mesma região).

### Postgres não conecta a partir do meu computador
Adicione seu IP em "Networking" → "Firewall rules" do Postgres.

### Function App não vê secrets do Key Vault
Verifique:
1. Managed Identity está ON
2. Role assignment "Key Vault Secrets User" foi atribuído
3. Pode levar até 5 minutos para propagar

### Certificado não valida no Entra ID
- Garanta que está fazendo upload do `.cer` (público), não do `.pfx`
- O thumbprint deve ser SHA-1 ou SHA-256, ambos aceitos
