# KPIs — Definições Matemáticas

> Este documento define **com precisão matemática** cada KPI da plataforma. Toda implementação em `MetricsCalculator` deve seguir literalmente estas definições. Mudanças exigem versão nova de cálculo (`metrics_calc_version`) e podem invalidar comparações longitudinais.

---

## 1. Convenções

### Universo de e-mails

Todas as métricas operam sobre o universo de e-mails que satisfazem **todos** os seguintes critérios:

- `email_messages.is_excluded = false`
- `email_classifications` existe (foi classificado pela IA)
- `email_messages.client_id IS NOT NULL` (cliente resolvido)
- `email_messages.deleted_at IS NULL` (não soft-deleted)

E-mails marcados como `direction_class = INTERNAL` ou `direction_class = OTHER` são **excluídos** das métricas relacionadas a clientes.

### Período padrão

Quando não especificado, "período" = **últimas 4 semanas completas (segunda a domingo)**, em fuso `America/Sao_Paulo`.

### Granularidade de cliente

Por padrão, métricas agregam por **conta (cliente)**. Drill-down disponível para:
- Carteira (agregação superior)
- Contato individual (agregação inferior)

### Filtros padrão

- **Status do cliente:** apenas clientes com `status = ACTIVE` (clientes ativos)
- Prospects e inativos disponíveis em filtro opcional

---

## 2. KPI Principal — Índice de Esforço Não-Solicitado

### Definição

Percentual dos e-mails enviados aos clientes que são proativos não-contratados, em threads iniciadas por nós, sem resposta do cliente em 7 dias.

### Fórmula

```
IENS = (E_unsolicited / E_outbound_total) × 100

onde:
E_unsolicited = e-mails que satisfazem TODAS as condições:
  - direction_class = OUTBOUND_PROACTIVE
  - proactive_subcategory ≠ PROACTIVE_CONTRACTED
  - thread.thread_initiator = THREAD_INITIATED_US
  - sent_at + 7 dias < NOW() E não há e-mail INBOUND da mesma thread/cliente
    enviado entre [sent_at, sent_at + 7 dias]

E_outbound_total = e-mails com direction_class IN (OUTBOUND_PROACTIVE, OUTBOUND_REACTIVE)
```

### Interpretação

- **0-15%**: equilíbrio saudável
- **15-30%**: atenção
- **30%+**: alta proporção de comunicação não-solicitada

### Granularidades suportadas

- Total da empresa
- Por carteira
- Por cliente
- Por gerente comercial (caixa monitorada)

### Restrições

- Não calcular para clientes com menos de 5 e-mails outbound no período (significância estatística mínima)
- E-mails com `sent_at` há menos de 7 dias são excluídos do numerador (ainda não há janela completa de resposta)

---

## 3. KPI 1.2 — Razão Proativo/Reativo

### Definição

Para cada e-mail nosso de resposta (reativo), quantos enviamos sem ter sido provocados (proativo)?

### Fórmula

```
RPR = E_proactive / E_reactive

onde:
E_proactive = count(direction_class = OUTBOUND_PROACTIVE)
E_reactive = count(direction_class = OUTBOUND_REACTIVE)
```

### Interpretação

- **< 0.5**: time muito reativo (pode ser bom — ouvir o cliente — ou ruim — passivo)
- **0.5 - 1.5**: equilíbrio
- **> 1.5**: time muito proativo (pode indicar empurrar demais)

### Tratamento de denominador zero

Se `E_reactive = 0` e `E_proactive > 0`, retornar valor especial `INF`. Em dashboards, exibir como "∞ (sem reativos)".

---

## 4. KPI 1.3 — Taxa de Iniciativa Própria

### Definição

% de threads iniciadas por nós no período.

### Fórmula

```
TIP = (T_us / T_total) × 100

onde:
T_us = count(threads com thread_initiator = THREAD_INITIATED_US 
              E first_message_at no período)
T_total = count(threads com first_message_at no período 
                E thread_initiator IN (THREAD_INITIATED_US, THREAD_INITIATED_CLIENT))
```

Threads com `thread_initiator = THREAD_INITIATED_UNCLEAR` são excluídas.

### Interpretação

- **< 30%**: cliente é quem busca a empresa (relação puxada por demanda)
- **30-60%**: equilíbrio
- **> 60%**: relação puxada por nós

---

## 5. KPI 2.1 — Taxa de Resposta a Proativos

### Definição

% de e-mails proativos nossos que receberam resposta do cliente em até 7 dias.

### Fórmula

```
TRP = (E_responded / E_proactive_total) × 100

onde:
E_proactive_total = count(direction_class = OUTBOUND_PROACTIVE 
                           E sent_at <= NOW() - 7 dias)
E_responded = count(e-mails de E_proactive_total que têm pelo menos 
                    um INBOUND da mesma thread com sent_at no intervalo
                    [proactive.sent_at, proactive.sent_at + 7 dias])
```

### Interpretação

- **< 30%**: maioria dos proativos é ignorada (sinal forte de "ninguém pediu")
- **30-60%**: engajamento moderado
- **> 60%**: proativos relevantes para o cliente

---

## 6. KPI 2.2 — Tempo Médio de Resposta do Cliente

### Definição

Quando enviamos algo (proativo ou reativo) e o cliente responde, quanto tempo ele leva em média?

### Fórmula

```
TMRC = AVG(t_resposta_cliente) em horas úteis

para cada par (e-mail nosso, próxima resposta INBOUND da mesma thread):
  t_resposta_cliente = horas_uteis(cliente_response.sent_at - nosso_email.sent_at)
```

**"Horas úteis"** = segunda a sexta, 09:00-18:00 em `America/Sao_Paulo`.

Pares onde o cliente não respondeu nunca são **excluídos do cálculo** (ver KPI 2.1 para taxa de não-resposta).

---

## 7. KPI 2.3 — Tempo Médio de Resposta Nossa

### Definição

Quando o cliente nos manda algo, quanto tempo levamos em média para responder?

### Fórmula

```
TMRN = AVG(t_resposta_nossa) em horas úteis

para cada par (e-mail INBOUND, próximo OUTBOUND da mesma thread):
  t_resposta_nossa = horas_uteis(nosso.sent_at - cliente.sent_at)
```

Threads em que não respondemos são contabilizadas separadamente como "Taxa de Não-Resposta Nossa".

### Métrica complementar — Taxa de Não-Resposta Nossa

```
TNRN = (E_unanswered / E_inbound_total) × 100

onde:
E_inbound_total = count(direction_class = INBOUND E sent_at <= NOW() - 7 dias)
E_unanswered = count(INBOUNDs sem OUTBOUND posterior na mesma thread em 7 dias)
```

---

## 8. KPI 3.1 — Mix de Proatividade

### Definição

Distribuição percentual dos e-mails proativos entre as 5 subcategorias.

### Fórmula

Para cada subcategoria `S` em [`PROACTIVE_CONTRACTED`, `PROACTIVE_OPPORTUNITY`, `PROACTIVE_RELATIONSHIP`, `PROACTIVE_OPERATIONAL`, `PROACTIVE_OTHER`]:

```
Mix(S) = (count(proactive_subcategory = S) / E_proactive_total) × 100
```

### Interpretação

Não há "bom" ou "ruim" universal. A leitura depende do negócio:

- Alto `PROACTIVE_CONTRACTED`: muita comunicação operacional contratada (esperado em modelo de serviço recorrente)
- Alto `PROACTIVE_OPERATIONAL`: muito problema operacional surgindo (pode indicar atrito no produto/serviço)
- Alto `PROACTIVE_OPPORTUNITY`: time vendendo ativamente
- Alto `PROACTIVE_RELATIONSHIP`: muito follow-up — combinado com baixa Taxa de Resposta = sinal de "encher caixa"

---

## 9. KPI 3.2 — Densidade de Comunicação por Cliente

### Definição

Volume médio de e-mails (qualquer direção) por cliente por dia útil no período.

### Fórmula

```
DCC(cliente) = E_total(cliente) / dias_uteis_no_periodo

onde:
E_total(cliente) = count(direction_class IN 
                          (INBOUND, OUTBOUND_PROACTIVE, OUTBOUND_REACTIVE)
                          E client_id = cliente)
```

### Uso

Identificar clientes outliers — quem consome desproporcionalmente o tempo da equipe. Útil para análise de ROI por cliente.

---

## 10. KPI 4.1 — Comparativo de Proatividade por Gerente

### Definição

Índice de Esforço Não-Solicitado (KPI principal) calculado por caixa monitorada (gerente).

### Fórmula

Mesma fórmula do KPI principal, agrupada por `mailbox_id` ao invés de empresa toda.

### Granularidade

- Cada caixa monitorada
- Cada carteira (média ponderada das caixas da carteira)

### Cuidado de governança

Esta métrica é **politicamente sensível**. Por padrão, dashboards executivos mostram **agregado por carteira**. Drill-down até nível individual exige clique consciente do admin/diretoria.

---

## 11. KPI 4.2 — Cobertura de Carteira

### Definição

% de clientes da carteira do gerente que tiveram pelo menos 1 e-mail no período.

### Fórmula

```
CC(gerente) = (clientes_com_atividade / total_clientes_da_carteira) × 100

onde:
clientes_com_atividade = count(distinct client_id em e-mails da caixa do gerente no período)
total_clientes_da_carteira = count(clients onde portfolio_id = gerente.portfolio_id 
                                    E status = ACTIVE 
                                    E deleted_at IS NULL)
```

### Interpretação

- **< 50%**: gerente está concentrando esforço em poucos clientes
- **50-80%**: cobertura moderada
- **> 80%**: gerente atende toda a carteira

---

## 12. Alertas (não-KPIs)

Alertas são **flags qualitativos**, não números agregados. São registrados na tabela `alerts` durante o cálculo semanal e exibidos nos dashboards.

### Alerta 1 — Cliente Abandonado

**Condição:**
```
last_communication_with_client(cliente) < NOW() - 30 dias
AND cliente.status = ACTIVE
```

**Severidade:** alta (vermelho)

---

### Alerta 2 — Cliente Sobrecomunicado

**Condição:**
```
COUNT(direction_class = OUTBOUND_PROACTIVE 
      AND proactive_subcategory ≠ PROACTIVE_CONTRACTED 
      AND sem resposta INBOUND em 7 dias 
      AND sent_at no último mês) >= 5 para o cliente
```

**Severidade:** média (amarelo)

---

### Alerta 3 — Gerente Sumido

**Condição:**
```
caixa.is_active = true
AND COUNT(e-mails OUTBOUND nos últimos 7 dias) = 0
```

**Severidade:** alta (vermelho)

---

### Alerta 4 — Cliente Reativo Crônico

**Condição:**
```
Para um cliente:
  TODAS as threads do último mês têm thread_initiator = THREAD_INITIATED_CLIENT
  AND COUNT(threads do último mês) >= 3
```

**Significado:** o cliente é quem sempre puxa a comunicação, possivelmente porque está insatisfeito ou tem demanda alta não atendida proativamente.

**Severidade:** média (amarelo)

---

## 13. Snapshot Semanal

Os KPIs são calculados **toda segunda-feira de manhã** sobre o período "últimas 4 semanas completas" e armazenados em:

- `metrics_weekly_client` — granularidade cliente
- `metrics_weekly_portfolio` — granularidade carteira
- `metrics_weekly_mailbox` — granularidade caixa/gerente

Cada linha tem `snapshot_date` (data da segunda-feira em que foi calculado) e `period_start_date`, `period_end_date` (janela analisada).

Snapshots antigos são preservados (sem soft-delete) para permitir séries temporais e comparativos históricos.

---

## 14. Versionamento de Cálculo

A versão atual é `metrics_calc_version = 1.0`.

Mudanças que **alteram** a versão:
- Mudança de fórmula de qualquer KPI
- Mudança de critério de exclusão (universo de e-mails)
- Mudança de definição de período padrão

Mudanças que **NÃO** alteram:
- Adicionar novo KPI
- Adicionar nova granularidade de drill-down
- Mudar visualização sem mudar fórmula

Cada snapshot armazena qual versão de cálculo foi usada. Comparações longitudinais entre versões devem ser feitas com cautela ou bloqueadas no front-end.

---

## 15. Referência cruzada

Os KPIs implementados em `src/services/metrics/calculator.py` devem ter docstring referenciando este documento e a seção específica. Exemplo:

```python
def calculate_unsolicited_effort_index(self, client_id: UUID, period: Period) -> float:
    """
    Calcula o Índice de Esforço Não-Solicitado.
    
    Ver docs/kpis.md, seção 2.
    """
```
