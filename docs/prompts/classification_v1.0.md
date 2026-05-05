# Prompt de Classificação — Versão 1.0

> Versão inicial sem few-shot examples. Após calibração (Fase 4), gera-se a versão 1.1 com 10-15 exemplos validados.

---

## Metadata

| Campo | Valor |
|-------|-------|
| `version` | `1.0` |
| `prompt_type` | `CLASSIFICATION` |
| `model_target` | `gpt-4o-mini` |
| `escalation_model` | `gpt-4o` |
| `escalation_threshold` | `confidence < 0.7` |
| `created_at` | (data do M18) |
| `taxonomy_version` | `1.0` |
| `notes` | Versão inicial baseline. Sem few-shot. |

---

## System Prompt

```
Você é um classificador especializado em análise de comunicação corporativa
por e-mail entre a Simple Energy (empresa brasileira do setor de energia)
e seus clientes corporativos.

Sua tarefa é classificar cada e-mail em três níveis e responder em JSON
estruturado válido.

================================================================
NÍVEL A — Direção do e-mail (sempre obrigatório)
================================================================

INBOUND
  Cliente externo escreveu para a empresa.
  Remetente é de domínio externo de cliente; destinatário inclui
  caixa monitorada interna.

OUTBOUND_REACTIVE
  Empresa escreveu ao cliente em RESPOSTA a algo prévio.
  Critério: existe e-mail anterior do cliente na thread, OU o e-mail
  menciona explicitamente um contato off-line anterior (ligação, reunião,
  WhatsApp, presencial).

OUTBOUND_PROACTIVE
  Empresa escreveu ao cliente sem ter sido provocada.
  Critério: não há e-mail anterior do cliente na thread E não há
  menção a contato off-line anterior.

INTERNAL
  Comunicação interna da empresa (todos os participantes são internos).
  
OTHER
  Auto-respostas, newsletters, notificações de sistemas, fornecedores,
  spam, ou casos com confiança < 0.5.

================================================================
NÍVEL C — Subcategoria (apenas se NÍVEL A = OUTBOUND_PROACTIVE)
================================================================

PROACTIVE_CONTRACTED
  Comunicação periódica esperada e contratada (relatório mensal,
  NF, boleto, relatório de andamento contratual).
  Use quando o e-mail corresponde a uma comunicação contratada
  cadastrada para este cliente (ver lista no contexto).

PROACTIVE_OPPORTUNITY
  Oferta comercial, novidade de produto, upsell, cross-sell.
  Conteúdo busca gerar receita ou expandir relacionamento.

PROACTIVE_RELATIONSHIP
  Manutenção de relacionamento, follow-up, status update não solicitado.
  Não tem oferta comercial direta nem demanda operacional urgente.

PROACTIVE_OPERATIONAL
  Comunicação operacional sobre projeto/serviço em andamento.
  Comunica algo que o cliente precisa saber agora (incidente, atraso,
  problema identificado).

PROACTIVE_OTHER
  Não se encaixa nas anteriores. Use com parcimônia.

================================================================
SINAIS DE REATIVIDADE OFFLINE
================================================================

Se você detectar marcadores que indicam que o e-mail é resposta a
contato off-line, classifique como OUTBOUND_REACTIVE mesmo sem e-mail
anterior na thread, e marque is_offline_reactive = true.

Marcadores típicos (não exaustivo):
  - "conforme falamos por telefone"
  - "seguindo nossa conversa por WhatsApp"
  - "atendendo sua solicitação na reunião de hoje"
  - "conforme combinado em call"
  - "conforme nossa reunião"
  - "respondendo ao seu pedido por telefone"
  - "conforme conversamos pessoalmente"
  - "seguindo o que conversamos"
  - "as per our call"
  - "following up on our meeting"

Salve os marcadores específicos detectados em detected_offline_markers.

================================================================
REGRAS IMPORTANTES
================================================================

1. Considere o histórico da thread fornecido. Se a thread já tem
   mensagens prévias do cliente, novos e-mails nossos são REACTIVE.

2. Considere as Comunicações Contratadas cadastradas para este cliente.
   Se o conteúdo corresponde a uma delas, classifique como
   PROACTIVE_CONTRACTED.

3. Threads com 5+ mensagens em andamento: novos e-mails nossos são
   sempre REACTIVE (parte de conversa ativa).

4. Auto-respostas ("estou de férias", "I'm out of office") classifique
   como OTHER.

5. Se o conteúdo está incompleto, ininteligível, ou você não consegue
   determinar com confiança ≥ 0.5, retorne OTHER com baixa confiança.

6. NÃO chute. Prefira confiança baixa a classificação errada.

7. reasoning_brief deve ter no MÁXIMO 20 palavras, em português, e
   explicar o critério principal da decisão.

================================================================
FORMATO DE RESPOSTA — JSON estrito
================================================================

Responda APENAS com um JSON válido, sem texto adicional, sem markdown,
sem code blocks. O JSON deve ter EXATAMENTE estes campos:

{
  "direction_class": "INBOUND" | "OUTBOUND_REACTIVE" | "OUTBOUND_PROACTIVE" | "INTERNAL" | "OTHER",
  "proactive_subcategory": "PROACTIVE_CONTRACTED" | "PROACTIVE_OPPORTUNITY" | "PROACTIVE_RELATIONSHIP" | "PROACTIVE_OPERATIONAL" | "PROACTIVE_OTHER" | null,
  "is_offline_reactive": true | false,
  "detected_offline_markers": ["string", ...],
  "confidence_score": 0.0 a 1.0,
  "reasoning_brief": "string"
}

Regras de validação:
  - proactive_subcategory deve ser não-null SE direction_class = OUTBOUND_PROACTIVE
  - proactive_subcategory deve ser null para qualquer outro direction_class
  - is_offline_reactive só pode ser true se direction_class = OUTBOUND_REACTIVE
  - confidence_score é float entre 0.0 e 1.0
  - detected_offline_markers é array (vazio se nenhum)
```

---

## User Prompt Template

```
Classifique o e-mail abaixo seguindo as instruções do sistema.

================================================================
CONTEXTO DA CAIXA QUE ENVIOU/RECEBEU
================================================================

Gerente comercial responsável: {{mailbox_owner_name}}
E-mail da caixa: {{mailbox_email}}
Carteira: {{portfolio_name}}
Descrição da carteira: {{portfolio_description}}

================================================================
CONTEXTO DO CLIENTE
================================================================

Nome do cliente: {{client_name}}
Status: {{client_status}}  (ACTIVE | PROSPECT | INACTIVE)
Carteira do cliente: {{client_portfolio_name}}

Comunicações Contratadas cadastradas com este cliente:
{{contracted_communications_list_or_none}}

(Se "Nenhuma cadastrada", não use PROACTIVE_CONTRACTED a menos que
o conteúdo seja inequívoco como NF, boleto, relatório formal recorrente.)

================================================================
CONTEXTO DA THREAD
================================================================

ID da conversa: {{conversation_id}}
Total de mensagens anteriores nesta thread: {{previous_message_count}}

{{thread_context}}

(Se previous_message_count = 0, esta é a primeira mensagem visível
na thread. Avalie se há marcadores de reatividade offline.)

(Se previous_message_count >= 5, a thread está madura e provavelmente
este e-mail é REACTIVE.)

================================================================
E-MAIL A CLASSIFICAR
================================================================

De: {{from_address}} ({{from_display_name}})
Para: {{to_addresses}}
CC: {{cc_addresses_or_none}}
Data: {{sent_at_iso}}
Assunto: {{subject}}

Corpo (limpo, truncado em 4000 chars):
---
{{body_clean}}
---

================================================================

Retorne APENAS o JSON conforme especificado.
```

---

## Variáveis do Template

| Variável | Tipo | Origem |
|----------|------|--------|
| `mailbox_owner_name` | string | `monitored_mailboxes.responsible_user_email` (resolvido para nome) |
| `mailbox_email` | string | `monitored_mailboxes.email_address` |
| `portfolio_name` | string | `portfolios.name` (carteira da caixa) |
| `portfolio_description` | string | `portfolios.description` (ou "N/A") |
| `client_name` | string | `clients.name` |
| `client_status` | string | `clients.status` |
| `client_portfolio_name` | string | `portfolios.name` (carteira do cliente) |
| `contracted_communications_list_or_none` | string | Lista formatada ou "Nenhuma cadastrada" |
| `conversation_id` | string | `email_messages.conversation_id` |
| `previous_message_count` | int | Count de mensagens anteriores na thread |
| `thread_context` | string | Resumo da thread (ver abaixo) |
| `from_address`, `from_display_name`, `to_addresses`, `cc_addresses_or_none`, `sent_at_iso`, `subject`, `body_clean` | string | Campos do e-mail |

---

## Formatação do `thread_context`

### Caso A — Thread tem 0 mensagens anteriores

```
Esta é a primeira mensagem da thread.
```

### Caso B — Thread tem 1 a 5 mensagens anteriores

Listar todas em ordem cronológica:

```
Mensagem 1 (CLIENTE, 2025-04-10 09:32):
"<primeiros 200 chars do body_clean>..."

Mensagem 2 (NÓS, 2025-04-10 14:15):
"<primeiros 200 chars do body_clean>..."

Mensagem 3 (CLIENTE, 2025-04-12 08:00):
"<primeiros 200 chars do body_clean>..."
```

### Caso C — Thread tem mais de 5 mensagens anteriores

Usar resumo recursivo armazenado em `email_threads.context_summary` + listar as 2 últimas mensagens:

```
Resumo da thread (geradoaté a 8ª mensagem):
"Cliente solicitou orçamento para projeto X. Após troca de informações
técnicas, recebeu proposta. Pediu ajustes. Recebeu versão revisada.
Aguardando aprovação."

Mensagens mais recentes:

Mensagem 9 (CLIENTE, 2025-04-20):
"<primeiros 200 chars>..."

Mensagem 10 (NÓS, 2025-04-21):
"<primeiros 200 chars>..."
```

---

## Formatação de `contracted_communications_list_or_none`

### Caso A — Cliente tem comunicações contratadas

```
- Relatório mensal de performance (mensal, dia 5)
- Boleto de cobrança (mensal, dia 25)
- Newsletter de mercado (semanal, segunda-feira)
```

### Caso B — Cliente sem comunicações contratadas

```
Nenhuma cadastrada
```

---

## Estimativa de tokens

Por chamada de classificação típica:

| Componente | Tokens estimados |
|------------|------------------|
| System prompt | ~750 |
| Contexto da caixa + cliente | ~80 |
| Comunicações contratadas | ~30 |
| Contexto da thread (caso B) | ~150 |
| E-mail (body 4k chars) | ~1000 |
| **Total input** | **~2010** |
| Output JSON | ~150 |
| **Total** | **~2160** |

Custo médio com gpt-4o-mini: ~$0.0004 por classificação.
Custo de 8.000 e-mails/mês: ~$3.

---

## Structured Outputs (Azure OpenAI)

Sempre usar `response_format` com schema enforced para garantir JSON válido:

```python
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "EmailClassification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "direction_class": {
                    "type": "string",
                    "enum": ["INBOUND", "OUTBOUND_REACTIVE", "OUTBOUND_PROACTIVE", "INTERNAL", "OTHER"]
                },
                "proactive_subcategory": {
                    "type": ["string", "null"],
                    "enum": ["PROACTIVE_CONTRACTED", "PROACTIVE_OPPORTUNITY", "PROACTIVE_RELATIONSHIP", "PROACTIVE_OPERATIONAL", "PROACTIVE_OTHER", None]
                },
                "is_offline_reactive": {"type": "boolean"},
                "detected_offline_markers": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "confidence_score": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "reasoning_brief": {"type": "string", "maxLength": 200}
            },
            "required": ["direction_class", "proactive_subcategory", "is_offline_reactive", "detected_offline_markers", "confidence_score", "reasoning_brief"],
            "additionalProperties": False
        }
    }
}
```

Atenção: nem todos os modelos do Azure OpenAI suportam `strict: True` em todas as regiões. Validar na implementação. Como fallback, usar `response_format = {"type": "json_object"}` e validar o output com Pydantic após receber.

---

## Validação de output (pós-LLM)

Mesmo com structured outputs, validar com Pydantic para garantir consistência semântica:

```python
class EmailClassificationResponse(BaseModel):
    direction_class: Literal["INBOUND", "OUTBOUND_REACTIVE", "OUTBOUND_PROACTIVE", "INTERNAL", "OTHER"]
    proactive_subcategory: Optional[Literal["PROACTIVE_CONTRACTED", "PROACTIVE_OPPORTUNITY", "PROACTIVE_RELATIONSHIP", "PROACTIVE_OPERATIONAL", "PROACTIVE_OTHER"]]
    is_offline_reactive: bool
    detected_offline_markers: list[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning_brief: str = Field(max_length=200)
    
    @model_validator(mode="after")
    def validate_subcategory_consistency(self):
        if self.direction_class == "OUTBOUND_PROACTIVE":
            if self.proactive_subcategory is None:
                raise ValueError("proactive_subcategory required for OUTBOUND_PROACTIVE")
        else:
            if self.proactive_subcategory is not None:
                raise ValueError("proactive_subcategory must be null when direction_class != OUTBOUND_PROACTIVE")
        
        if self.is_offline_reactive and self.direction_class != "OUTBOUND_REACTIVE":
            raise ValueError("is_offline_reactive can only be true when direction_class = OUTBOUND_REACTIVE")
        
        return self
```

---

## Estratégia de Escalada

```
1. Chamar gpt-4o-mini com este prompt
2. Validar response com Pydantic
3. Se confidence_score >= 0.7: aceitar e persistir
4. Se confidence_score < 0.7: re-chamar com gpt-4o (mesmo prompt)
5. Persistir resultado da segunda chamada com flag was_escalated = true
6. Se ainda confidence < 0.7 após gpt-4o: marcar para revisão humana
```

Implementação detalhada em `src/services/classification/classifier.py` (M18).

---

## Próximas versões

**v1.1** (após Fase 4 — calibração):
- Adicionar 10-15 few-shot examples baseados em revisões humanas
- Refinar instruções com base em padrões de erro observados
- Manter mesma estrutura de output

**v2.0** (futuro, fora do MVP):
- Suporte a outros idiomas (inglês corporativo)
- Detecção de sentimento (campo opcional)
- Detecção de urgência (campo opcional)

---

## Histórico de Mudanças

| Versão | Data | Autor | Mudança |
|--------|------|-------|---------|
| 1.0 | (data do M18) | Sistema | Versão inicial |
