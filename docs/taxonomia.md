# Taxonomia de Classificação — Proativo / Reativo

> Este é o documento mais importante do projeto do ponto de vista de domínio. Todas as métricas, dashboards e decisões de negócio derivam das definições aqui contidas. Mudanças neste documento exigem revisão da diretoria e gera nova versão de prompt.

---

## 1. Filosofia da Taxonomia

A taxonomia foi desenhada para responder à pergunta-chefe da diretoria:

> "Estamos sendo proativos demais com clientes que não pediram nada?"

Para responder com precisão, classificamos cada e-mail em **três níveis** complementares:

- **Nível A** — Direção do e-mail (quem escreveu para quem)
- **Nível B** — Iniciativa da thread (quem começou a conversa)
- **Nível C** — Subcategoria de proatividade (qual o tipo de proativo, quando aplicável)

Os três níveis em conjunto permitem distinguir, por exemplo:

- "Boa proatividade" (relatório mensal contratado, esperado pelo cliente)
- "Proatividade comercial estratégica" (oferta de novo produto)
- "Proatividade não-solicitada" (insistência em algo que o cliente não pediu)

---

## 2. Nível A — Direção do E-mail

Cada e-mail é classificado em uma e apenas uma das seguintes categorias:

### `INBOUND`
Cliente escreveu para nós.

**Critérios:**
- O remetente (`from`) pertence a domínio de cliente externo
- Ao menos um destinatário (`to` ou `cc`) é uma caixa monitorada nossa

**Exemplos:**
- joao@acme.com escreve para maria@simpleenergy.com.br
- joao@acme.com escreve para [maria, carlos]@simpleenergy.com.br

---

### `OUTBOUND_REACTIVE`
Nós escrevemos ao cliente em resposta a algo.

**Critérios:**
- O remetente é uma caixa monitorada nossa
- O destinatário é cliente externo
- Existe uma das condições abaixo:
  - Há e-mail anterior do cliente na mesma thread (`conversationId`)
  - O conteúdo do e-mail menciona explicitamente um contato off-line anterior (sinais de **reatividade offline** — ver seção 4)

**Exemplos:**
- Resposta direta a um e-mail de joao@acme.com
- E-mail novo para joao@acme.com começando com "Conforme nossa call hoje pela manhã..."

---

### `OUTBOUND_PROACTIVE`
Nós escrevemos ao cliente sem ter sido provocados.

**Critérios:**
- O remetente é uma caixa monitorada nossa
- O destinatário é cliente externo
- **Nenhuma** das condições abaixo se aplica:
  - Há e-mail anterior do cliente na thread
  - O conteúdo menciona contato off-line anterior

**Exemplos:**
- E-mail novo para joao@acme.com com proposta comercial não solicitada
- E-mail enviando relatório mensal contratado
- Follow-up "alguma novidade sobre a proposta?" sem que o cliente tenha respondido

Quando classificado como `OUTBOUND_PROACTIVE`, o **Nível C** deve ser preenchido obrigatoriamente.

---

### `INTERNAL`
Comunicação interna da empresa.

**Critérios:**
- Remetente e todos os destinatários (`to` e `cc`) pertencem a domínios da própria empresa
- Domínios internos cadastrados em tabela de configuração

**Tratamento:** **excluído de todas as métricas de comunicação com cliente.** É contado apenas para análises operacionais internas (futuro).

**Exemplos:**
- maria@simpleenergy.com.br escreve para carlos@simpleenergy.com.br
- maria@simpleenergy.com.br para diretoria@simpleenergy.com.br

---

### `OTHER`
Não se encaixa nas categorias acima ou é tráfego "lixo".

**Critérios (qualquer um):**
- Auto-respostas (out-of-office, entrega de e-mail)
- Newsletters, marketing massivo
- Notificações de sistemas (LinkedIn, faturas de SaaS, alertas)
- Spam não filtrado
- Comunicação com fornecedores (não-clientes)
- Casos onde o LLM não consegue determinar a categoria com confiança ≥ 0.5

**Tratamento:** **excluído de todas as métricas.**

**Detecção automática (antes do LLM):**
- Headers `Auto-Submitted: auto-replied`, `X-Auto-Response-Suppress`
- Padrões textuais: "Estou de férias", "I'm out of office", "This is an automated message"
- Remetentes de domínios marcados como "automatizados" (configurável)

---

## 3. Nível B — Iniciativa da Thread

Cada **thread** (não cada e-mail individualmente) recebe uma classificação de iniciativa:

### `THREAD_INITIATED_US`
A primeira mensagem da thread foi enviada por nós.

### `THREAD_INITIATED_CLIENT`
A primeira mensagem da thread foi enviada pelo cliente.

### `THREAD_INITIATED_UNCLEAR`
Casos em que a primeira mensagem disponível não pode ser determinada (ex: thread truncada na ingestão).

**Como é determinado:**
A partir do `conversationId` do Graph, ordenamos as mensagens por `sentDateTime` ASC e olhamos quem é o remetente da primeira. Se o remetente é interno, `THREAD_INITIATED_US`. Se externo, `THREAD_INITIATED_CLIENT`.

**Cuidado importante:** se a thread tem mensagens anteriores ao período da nossa janela histórica, pode ser que estejamos vendo "metade" da conversa. Nesse caso, marcamos como `THREAD_INITIATED_UNCLEAR` e excluímos das métricas de iniciativa.

---

## 4. Nível C — Subcategoria de Proativo

Aplicado apenas quando Nível A = `OUTBOUND_PROACTIVE`.

### `PROACTIVE_CONTRACTED`
Comunicação periódica esperada e contratada com o cliente.

**Critérios:**
- O cliente em questão tem cadastro de "Comunicação Contratada" no painel admin que descreve esse tipo de envio
- O conteúdo do e-mail é compatível com a descrição cadastrada

**Exemplos:**
- Relatório mensal de performance enviado todo dia 5
- Nota fiscal eletrônica
- Boleto de cobrança recorrente
- Relatório semanal de andamento contratual

**Importância:** este subtipo é **excluído** da métrica chefe (Índice de Esforço Não-Solicitado). É proativo, mas é proativo "esperado".

---

### `PROACTIVE_OPPORTUNITY`
Oferta comercial, novidade de produto, upsell ou cross-sell.

**Critérios:**
- O conteúdo apresenta produto, serviço, oferta ou condição comercial
- Tem intenção clara de gerar nova receita ou expandir relacionamento

**Exemplos:**
- "Lançamos um novo produto que pode interessar à ACME"
- "Temos uma promoção até dia 30 que poderia ser interessante"
- "Quero apresentar uma solução adicional para vocês"

---

### `PROACTIVE_RELATIONSHIP`
Manutenção de relacionamento, follow-up, status update não solicitado.

**Critérios:**
- O conteúdo busca manter contato, atualizar status, demonstrar atenção
- Não há oferta comercial direta
- Não há demanda operacional urgente

**Exemplos:**
- "Tudo bem? Há quanto tempo. Como vão as coisas por aí?"
- "Só passando para confirmar que o projeto X está em andamento conforme combinado"
- "Alguma novidade sobre a proposta que enviamos no mês passado?"

---

### `PROACTIVE_OPERATIONAL`
Comunicação operacional sobre projeto/serviço em andamento que precisamos comunicar proativamente.

**Critérios:**
- O conteúdo trata de operação atual com o cliente
- Comunica algo que o cliente precisa saber (mas não pediu agora)
- Não é parte de uma comunicação periódica contratada

**Exemplos:**
- "Houve uma indisponibilidade no sistema X hoje, já normalizada"
- "Preciso te informar que o entregável Y vai atrasar 2 dias"
- "Identificamos um problema no projeto e estamos trabalhando para resolver"

---

### `PROACTIVE_OTHER`
Não se encaixa nas anteriores.

**Uso:** caso de exceção. Se 5%+ dos proativos cair aqui, revisar a taxonomia.

---

## 5. Reatividade Offline

Um caso especial e importante: e-mails que tecnicamente parecem proativos (não há e-mail anterior na thread) mas são na verdade reativos a um contato off-line (ligação, reunião, WhatsApp, encontro presencial).

### Marcadores textuais a detectar

O LLM deve buscar por padrões similares a:

**Português:**
- "conforme falamos por telefone"
- "seguindo nossa conversa por WhatsApp"
- "atendendo sua solicitação na reunião de hoje/ontem"
- "conforme combinado em call"
- "conforme nossa reunião"
- "respondendo ao seu pedido por telefone"
- "conforme conversamos pessoalmente"
- "seguindo o que conversamos"

**Inglês (eventual):**
- "as per our call"
- "following up on our meeting"
- "as discussed by phone"

### Tratamento

Quando o LLM detectar marcador de reatividade offline:

1. Classificar como `OUTBOUND_REACTIVE` (não `OUTBOUND_PROACTIVE`)
2. Marcar `is_offline_reactive = true`
3. Salvar os marcadores detectados em `detected_offline_markers` (array)

Isso permite, posteriormente, analisar o volume de comunicação que é "puxada" por canais não-e-mail.

---

## 6. Casos de Borda e Decisões

### 6.1 Cliente em CC (não em To)
**Decisão:** trata da mesma forma que estar em To. Para fins de classificação, qualquer destinatário externo de cliente conta.

### 6.2 Múltiplos clientes no destinatário
**Decisão:** o e-mail é registrado uma vez, mas associado ao **cliente principal** (regra: To primeiro, CC depois; entre múltiplos, o cliente com maior frequência histórica naquela caixa). Se ambíguo, marca cliente como "MULTIPLE" (analisar caso a caso).

### 6.3 Encaminhamento (forward)
**Decisão:** o e-mail é classificado pela direção do **último envio** (quem encaminhou e para quem). O conteúdo encaminhado anteriormente é parte do contexto, mas não muda a classificação do envio atual.

### 6.4 Resposta automática vs out-of-office
**Decisão:** ambas são `OTHER` (excluídas). Detecção via headers e padrões.

### 6.5 Thread com 30+ mensagens
**Decisão:** todas as mensagens após a primeira são `OUTBOUND_REACTIVE` ou `INBOUND` (nunca `OUTBOUND_PROACTIVE`). Uma vez que a thread está "quente", proativo só pode existir em thread nova.

### 6.6 Thread iniciada por nós com follow-up sem resposta
**Decisão:** o follow-up é `OUTBOUND_PROACTIVE` (subcategoria normalmente `PROACTIVE_RELATIONSHIP`), pois reativo exigiria ação do cliente. Múltiplos follow-ups sem resposta = sinal forte de "comunicação não solicitada".

### 6.7 Cliente novo (primeiro contato)
**Decisão:** se nós escrevemos primeiro, é `OUTBOUND_PROACTIVE` + `PROACTIVE_OPPORTUNITY` (ou `PROACTIVE_RELATIONSHIP` se for warm intro). Se o cliente escreveu primeiro (ex: lead de site), é `INBOUND` e nosso retorno é `OUTBOUND_REACTIVE`.

### 6.8 Domínio interno mas pessoa não cadastrada
**Decisão:** se o domínio é interno (`@simpleenergy.com.br`), classificamos como interno mesmo sem cadastro do contato.

### 6.9 E-mail enviado para si mesmo (lembretes pessoais)
**Decisão:** `OTHER`, excluído.

### 6.10 Drafts e mensagens não enviadas
**Decisão:** ignorados na ingestão. Pasta `Drafts` é sempre excluída por padrão.

---

## 7. Atributos da Classificação

Cada e-mail classificado pela IA recebe os seguintes campos:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `direction_class` | enum | sim | Nível A |
| `proactive_subcategory` | enum | só se A=PROACTIVE | Nível C |
| `is_offline_reactive` | bool | sim | Marcado se detectou reatividade offline |
| `detected_offline_markers` | array[string] | sim | Marcadores detectados (vazio se nenhum) |
| `confidence_score` | float [0-1] | sim | Confiança do modelo |
| `reasoning_brief` | string | sim | Justificativa em até 20 palavras |
| `prompt_version` | string | sim | Versão do prompt usada |
| `model_used` | string | sim | gpt-4o-mini, gpt-4o, etc |

A iniciativa da thread (`thread_initiator`) é calculada separadamente, não pelo LLM, mas pelo `ThreadAnalyzer` baseado em ordenação cronológica.

---

## 8. Concordância e Calibração

A IA não é perfeita. A taxonomia depende de calibração humano-no-loop.

**Metas de concordância humano-IA:**

- **Nível A** (direção): ≥ 85% de concordância
- **Nível C** (subcategoria): ≥ 75% de concordância
- **Reatividade offline**: ≥ 80% (precisão na detecção)

**Threshold de confiança:**

- `confidence_score < 0.7` → escalada para modelo maior (gpt-4o)
- Mesmo após escalada, casos com confidence < 0.7 → fila de revisão humana

**Fluxo de calibração:** ver `docs/runbooks/calibracao_da_ia.md`.

---

## 9. Versionamento da Taxonomia

A taxonomia atual é **versão 1.0**.

Mudanças que **NÃO** alteram a versão:
- Adicionar marcadores de reatividade offline
- Refinar exemplos
- Esclarecer casos de borda

Mudanças que **alteram** a versão:
- Adicionar/remover categoria
- Mudar definição operacional de uma categoria
- Renomear enum

A versão da taxonomia está acoplada à versão do prompt. Mudança de taxonomia = novo prompt = re-classificação opcional do histórico.

---

## 10. Por que esta taxonomia?

A taxonomia foi desenhada para **separar três coisas que normalmente são confundidas**:

1. **Quem escreveu** (Nível A) — métrica básica de volume
2. **Quem começou** (Nível B) — métrica de iniciativa de relacionamento
3. **Por quê escrevemos** (Nível C) — métrica de natureza do esforço

Essa separação permite distinguir, por exemplo:

- "Time comercial atende muito" — alta proporção de OUTBOUND_REACTIVE → bom
- "Time comercial empurra demais" — alta proporção de OUTBOUND_PROACTIVE com subcategoria diferente de CONTRACTED → atenção
- "Cliente abandonou" — apenas threads INITIATED_US, sem INBOUND → alerta

Sem essa granularidade, a métrica vira uma média que esconde o problema real.
