# 06 — Motor de Regularização de Dívidas

**Objetivo:** especificar, de forma determinística e testável, como o sistema
calcula o orçamento disponível, ordena dívidas, projeta pagamentos e gera o
plano de regularização.

**Público:** produto, engenharia e QA.
**Versão do motor:** `1` (incrementar a cada mudança de regra que altere resultados).

> **Implementação:** `src/apps/plans/engine/` (tipos, taxas, ordenação e simulação).
> **Testes de ouro:** `tests/test_engine.py` (14 casos, incluindo os números desta doc).

---

## 1. Princípios

1. **Determinismo:** mesmos inputs + mesma versão ⇒ mesmos outputs.
2. **Explicabilidade:** cada ordem e valor tem justificativa rastreável.
3. **Realismo:** nunca sugerir pagamento que comprometa o mínimo existencial.
4. **Transparência:** juros, premissas e arredondamentos visíveis.
5. **Segurança:** plano inviável é dito com clareza, não escondido.
6. **Testabilidade:** funções puras, sem Django, com casos de ouro.

---

## 2. Entradas e saídas

### 2.1 Entradas

```text
Perfil:
  renda_liquida            Decimal >= 0
  despesas_essenciais      Decimal >= 0
  minimo_existencial       Decimal >= 0
  outras_despesas          Decimal >= 0   (planejadas, não essenciais)
  renda_bruta              Decimal | null (para DTI)

Dívidas (ativas):
  id, credor
  saldo_atual              Decimal >= 0
  taxa_mensal              Decimal (fração, ex.: 0.0199)
  parcela_minima           Decimal > 0
  vencimento (dia)         1..31
  prioridade_travada       int | null

Parâmetros:
  estrategia               avalanche | snowball | hybrid
  mes_inicial              date (dia 1)
  aporte_extra             Decimal (opcional)
  meses_aporte_extra       int (0 = único)
  limite_meses             600
  engine_version           1
```

### 2.2 Saídas

```text
Plano:
  status                   ok | inviavel | prazo_excedido
  ordem                    [debt_id, ...] com justificativa
  calendario               [{mes, debt_id, pagamento, juros, principal, saldo_final}]
  total_juros              Decimal
  total_pago               Decimal
  meses_ate_quitar         int
  data_quitacao            date
  primeiro_pagamento       {mes, debt_id, valor}
  avisos                   [ ... ]
  comparacao (opcional)    {avalanche, snowball, hybrid}
```

---

## 3. Fórmulas fundamentais

### 3.1 Conversão de taxas

Taxa mensal a partir da anual **efetiva**:

```
i_m = (1 + i_a)^(1/12) − 1
```

Exemplo: `i_a = 12% a.a.` → `i_m = 0,948879% a.m.` (fração `0.00948879...`).

Taxa anual a partir da mensal:

```
i_a = (1 + i_m)^12 − 1
```

**Taxa nominal anual** (quando o contrato diz "12% ao ano" sem capitalização
explícita): `i_m = i_nominal / 12`. O app deve pedir a taxa mensal ou o CET;
se o usuário informar anual, tratar como **efetiva** por padrão e exibir aviso
com opção de corrigir.

**CET:** usar como taxa efetiva anual total e converter por juros compostos.
Se o CET incluir tarifas e seguros, o valor é mais fiel ao custo real.

### 3.2 Juros do mês

```
juros_mes = round(saldo × i_m, 2)
saldo_com_juros = saldo + juros_mes
```

Arredondamento **half-up** em cada mês. O total de juros é a soma dos juros
mensais; não recalcular a partir do total para evitar divergência de centavos.

### 3.3 Parcela de amortização (sistema francês)

Para um saldo `P`, taxa `i` e `n` parcelas:

```
PMT = P × i / (1 − (1 + i)^(−n))
```

Se `i = 0`: `PMT = P / n`.

**Uso:** derivar parcela mínima quando o usuário informa apenas saldo, taxa e
prazo (ex.: renegociação).

### 3.4 Taxa implícita (dado saldo, parcela e prazo)

Quando o usuário informa parcela e prazo, mas não a taxa, resolver:

```
P = PMT × (1 − (1 + i)^(−n)) / i
```

Por **bisseção** em `i ∈ [0, 1]` (0% a 100% a.m.), pois a função é monotônica:

```
para 100 iterações:
    i_meio = (i_min + i_max) / 2
    pmt_calc = PMT(i_meio)
    se |pmt_calc − PMT| < 0.005: retornar i_meio
    se pmt_calc > PMT: i_max = i_meio
    senão: i_min = i_meio
```

Se não convergir ou ficar no limite, retornar `null` e pedir taxa manual.
**Nunca** inventar taxa silenciosamente.

### 3.5 Orçamento e saldo livre

```
piso_essencial = max(despesas_essenciais, minimo_existencial)
orcamento_dividas (B) = renda_liquida − piso_essencial − outras_despesas
soma_minimos (M) = Σ parcela_minima
saldo_livre (S) = B − M
```

> **Importante:** o motor consome `B` (total disponível para dívidas, incluindo
> os mínimos). O dashboard mostra `S` (o que sobra depois dos mínimos).
> Confundir os dois é o erro de implementação mais provável — cobrir com testes.

**Viabilidade:**

```
se B <= 0            → inviável (orçamento insuficiente)
se S < 0             → inviável (mínimos maiores que o orçamento)
se Σ juros_mes > B   → inviável/agravamento (dívida cresce em agregado)
```

**Risco de amortização negativa** (por dívida):

```
se parcela_minima <= saldo × i_m  → aviso crítico
```

O plano ainda pode quitá-la se o excedente for direcionado a ela; o motor deve
priorizá-la ou alertar que ela crescerá até ser atacada.

---

## 4. Estratégias de ordenação

### 4.1 Avalanche

```
ordenar por:
  1. taxa_mensal DESC
  2. saldo_atual ASC
  3. vencimento ASC
  4. id ASC (determinismo)
```

**Justificativa:** cada real extra abate a dívida mais cara, minimizando juros.

### 4.2 Snowball

```
ordenar por:
  1. saldo_atual ASC
  2. taxa_mensal DESC
  3. vencimento ASC
  4. id ASC
```

**Justificativa:** vitórias rápidas, menos credores, reforço comportamental.

### 4.3 Híbrida (padrão recomendado)

```
S = B − Σ mínimos
total_divida = Σ saldos

quick_wins = dívidas onde:
    saldo <= 2 × max(S, 0)
    OU saldo <= 10% × total_divida

ordenar quick_wins por saldo ASC (desempate: taxa DESC, vencimento, id)
restante = demais dívidas ordenadas por avalanche

ordem_final = quick_wins + restante
```

**Parâmetros configuráveis:** multiplicador (2), percentual (10%), limite de
quick wins (ex.: no máximo 3 dívidas ou 15% do total). Evitar que a fase 1
consuma todo o orçamento e atrase a dívida mais cara.

**Exemplo:** com `S = 370`, `total = 12.800`, a dívida de R$ 800 atende ao
critério de 10% (1.280) e entra como quick win, mesmo com `2 × S = 740`.

### 4.4 Dívidas travadas (`priority_locked`)

- Dívidas com `priority_locked` são posicionadas primeiro, na ordem do campo.
- O plano exibe aviso: "Você fixou esta dívida; isso pode custar mais juros."
- O motor calcula o custo da trava na comparação.
- Empate: ordem da estratégia.

### 4.5 Desempate e estabilidade

Sempre incluir `id` como último critério. Ordenações devem ser **estáveis** e
documentadas; mudanças de desempate exigem nova `engine_version`.

---

## 5. Algoritmo de simulação

### 5.1 Pseudocódigo

```python
def simular(entrada) -> Plano:
    validar(entrada)

    B = orcamento_dividas(entrada)          # inclui mínimos
    M = soma(parcela_minima)
    S = B - M

    if B <= 0 or S < 0:
        return Plano.inviavel(motivo="orçamento insuficiente")

    dividas = [d for d in entrada.dividas if d.saldo > 0]
    ordem = ordenar(dividas, entrada.estrategia, S, B)
    ativas = {d.id: d for d in dividas}

    total_juros = 0
    total_pago = 0
    calendario = []
    primeiro_pagamento = None

    para mes in 1..LIMITE_MESES:
        # 1. Juros
        para d em ordem:
            se ativas[d.id].saldo > 0:
                juros = round(saldo * d.taxa_mensal, 2)
                saldo += juros
                juros_mes[d.id] = juros
            senão:
                juros_mes[d.id] = 0

        disponivel = B + aporte_extra_do_mes(mes)

        # 2. Mínimos (todas as dívidas)
        para d em ordem:
            se ativas[d.id].saldo <= 0: continuar
            pago = min(d.parcela_minima, saldo, disponivel)
            saldo -= pago
            disponivel -= pago
            pagamento[d.id] += pago
            total_juros += juros_mes[d.id]
            total_pago += pago

        # 3. Excedente na ordem de prioridade
        para d em ordem:
            se disponivel <= 0: parar
            se ativas[d.id].saldo <= 0: continuar
            pago = min(disponivel, saldo)
            saldo -= pago
            disponivel -= pago
            pagamento[d.id] += pago
            total_pago += pago

        # 4. Registrar calendário e quitações
        para d em ordem:
            se pagamento[d.id] > 0:
                juros_pagos = min(juros_mes[d.id], pagamento[d.id])
                principal = pagamento[d.id] - juros_pagos
                capitalizado = juros_mes[d.id] - juros_pagos
                calendario.adicionar(
                    mes, d.id, pagamento[d.id], juros_mes[d.id],
                    principal, capitalizado, saldo_atual(d)
                )
                se primeiro_pagamento is None:
                    primeiro_pagamento = (mes, d.id, pagamento[d.id])
                pagamento[d.id] = 0

        # 5. Verificar fim
        se todas as dívidas com saldo <= 0.005:
            retornar Plano.ok(
                ordem, calendario, total_juros, total_pago,
                meses=mes, data_quitacao=mes_inicial + mes meses,
                primeiro_pagamento
            )

        # 6. Avisos de agravamento
        se saldo_total(mes) > saldo_total(mes-1):
            meses_agravamento += 1
            se meses_agravamento >= 3:
                aviso("dívida crescendo; revise orçamento ou renegocie")

    retornar Plano.prazo_excedido(ordem, calendario, ...)
```

### 5.2 Detalhes de implementação

| Tema | Regra |
|------|-------|
| Juros | Arredondar a cada mês (half-up), antes de pagar |
| Ordem de abatimento | Juros do mês → principal |
| Pagamento mínimo | Limitado ao saldo devedor |
| Excedente | Percorre a ordem, quitando e continuando com o troco |
| Rollover | Embutido: `B` é fixo; ao quitar, o mínimo liberado vira excedente |
| Saldo residual | Considerar quitado se `saldo <= 0.005` (meio centavo) |
| Conclusão | `data_quitacao = mes_inicial + meses` (1º dia após o último mês de pagamento) |
| Última parcela | Pagar o saldo exato; não gerar pagamento negativo |
| Aporte extra | Único no mês 1 ou recorrente por N meses |
| Limite | 600 meses; retornar `prazo_excedido` sem loop infinito |
| Determinismo | Ordenação com critério final `id` |
| Precisão | `Decimal` com contexto ≥ 28 dígitos; quantizar a 2 casas |

### 5.3 Complexidade

- Tempo: `O(meses × dívidas log dívidas)` para ordenar + `O(meses × dívidas)`.
- Espaço: `O(meses × dívidas)` para o calendário.
- Com 20 dívidas × 600 meses: ~12.000 linhas, < 300 ms em Python.
- Se necessário, otimizar com vetores e parar cedo quando só há uma dívida.

---

## 6. Exemplos verificados (casos de ouro)

> Números calculados com o algoritmo acima, arredondamento half-up.
> Servem de teste de regressão.

### 6.1 Uma dívida

Dívida: R$ 1.000,00 · 2% a.m. · mínimo R$ 100,00 · orçamento para dívidas `B = R$ 300,00`.

| Mês | Juros | Pagamento | Saldo final |
|-----|-------|-----------|-------------|
| 1 | 20,00 | 300,00 | 720,00 |
| 2 | 14,40 | 300,00 | 434,40 |
| 3 | 8,69 | 300,00 | 143,09 |
| 4 | 2,86 | 145,95 | 0,00 |

**Resultado:** 4 meses · juros R$ 45,95 · total pago R$ 1.045,95.

### 6.2 Três dívidas (B = R$ 1.200)

| Dívida | Saldo | Taxa a.m. | Mínimo |
|--------|-------|-----------|--------|
| Cartão | 6.000 | 1,99% | 300 |
| Empréstimo | 4.000 | 1,25% | 250 |
| Parcelado | 2.000 | 0,99% | 200 |

Mínimos = 750 · excedente = 450 · viável.

| Estratégia | Meses | Juros totais | Total pago | 1ª quitação |
|------------|-------|--------------|------------|-------------|
| Avalanche | 11 | R$ 1.112,02 | R$ 13.112,02 | mês 9 (Cartão) |
| Snowball | 12 | R$ 1.287,88 | R$ 13.287,88 | mês 4 (Parcelado) |
| Híbrida | 11* | ≈ R$ 1.112,02* | ≈ R$ 13.112,02* | mês 9* |

\* Sem dívida que atenda ao critério de quick win, a híbrida coincide com a avalanche.

**Leitura:** snowball custa R$ 175,86 a mais em juros, mas dá a primeira vitória
5 meses antes. É exatamente o trade-off que o app deve mostrar.

### 6.3 Quatro dívidas (B = R$ 1.200)

Acrescentando **Loja: R$ 800, 0,5% a.m., mínimo R$ 80**:

Mínimos = 830 · excedente = 370 · total = 12.800.

| Estratégia | Meses | Juros totais | Total pago | 1ª quitação |
|------------|-------|--------------|------------|-------------|
| Avalanche | 12 | R$ 1.230,45 | R$ 14.030,45 | mês 10 (Cartão) |
| Snowball | 12 | R$ 1.426,83 | R$ 14.226,83 | mês 2 (Loja) |
| Híbrida | 12 | R$ 1.288,01 | R$ 14.088,01 | mês 2 (Loja) |

**Leitura:** a híbrida custa R$ 57,56 a mais que a avalanche, mas entrega a
primeira vitória 8 meses antes e economiza R$ 138,82 vs. snowball. Por isso é a
recomendação padrão quando há quick wins.

### 6.4 Exemplo textbook (sem juros)

Dívidas A 250 (mín. 25), B 500 (26), C 2.500 (150), D 5.000 (200);
`B = 501` (mínimos 401 + 100 extra). Estratégia snowball.

| Quitação | Mês |
|----------|-----|
| A | 2 |
| B | 5 |
| C | 11 |
| D | 17 |

**Resultado:** 17 meses · juros R$ 0,00 · total pago R$ 8.250,00.
Confere com o exemplo clássico da literatura.

### 6.5 Casos de borda

| Caso | Entrada | Resultado esperado |
|------|---------|-------------------|
| Amortização negativa | Saldo 1.000, i = 10%, mínimo 100 | Aviso crítico; dívida não cai só com o mínimo |
| Inviável por mínimos | Mínimos 750, B = 500 | `inviavel`; não gerar calendário |
| Orçamento zero | B = 0 | `inviavel` |
| Taxa zero | Saldo 3.000, i = 0, mínimo 500 | 6 meses, juros 0 |
| Aporte extra maior que saldo | Saldo 300, extra 1.000 | Quita e redireciona o troco |
| Prazo > 600 | Mínimo 10, saldo 100.000, i 2% | `prazo_excedido` com aviso |
| Duas dívidas idênticas | Mesmo saldo/taxa | Ordem por `id`, determinística |

---

## 7. Comparação de estratégias

### 7.1 Métricas comparadas

| Métrica | Descrição |
|---------|-----------|
| Total de juros | Soma dos juros projetados |
| Total pago | Principal + juros |
| Meses até quitar | Duração do plano |
| Data de quitação | `mes_inicial + meses` |
| Primeira quitação | Mês e dívida da primeira vitória |
| Dívidas quitadas em 6 meses | Contagem |
| Dívidas quitadas em 12 meses | Contagem |
| Maior pagamento mensal | Pico de saída |
| Nº de credores ao fim de 6/12 meses | Redução |

### 7.2 Recomendação

```
se plano inviável:
    recomendar revisão de orçamento/renegociação (não recomendar estratégia)
senão se existe quick win:
    recomendar híbrida
senão:
    recomendar avalanche

exibir sempre:
    "A avalanche tende a economizar R$ X; a snowball antecipa a primeira
     quitação em Y meses. A híbrida equilibra os dois."
```

**Nunca** esconder o custo da estratégia escolhida. Se o usuário escolher
snowball, mostrar "você pagará R$ X a mais em juros, mas quitará sua primeira
dívida Y meses antes".

### 7.3 Custo da trava manual

Se o usuário fixar uma dívida, comparar com a ordem ótima e exibir:
"Essa escolha pode custar até R$ X em juros e adiar a quitação em Y meses."

---

## 8. Simulador de cenários

### 8.1 Corte de despesa

```
B_novo = B + corte_mensal
```

Recalcular. Exibir diferença de prazo, juros e primeira quitação.
Se `corte` tornar o orçamento inviável (ex.: cortar essencial), alertar.

### 8.2 Renda extra

```
B_novo(m) = B + renda_extra, para m <= meses_aporte
B_novo(m) = B, caso contrário
```

Se for aporte único, aplicar apenas no mês 1. Se o valor for maior que a dívida
prioritária, o troco segue para a próxima.

### 8.3 Renegociação

Entradas: dívida, desconto sobre saldo, nova taxa, novo prazo, entrada.

```
saldo_novo = saldo_atual × (1 − desconto) − entrada
i_novo = taxa_informada (mensal)
PMT_novo = PMT(saldo_novo, i_novo, n)
parcela_minima_nova = PMT_novo
```

Recalcular o plano com os novos parâmetros. Comparar:
"Renegociar reduz a parcela em R$ X, mas aumenta o total pago em R$ Y."
Se `i_novo >= i_atual` e prazo maior, alertar sobre custo total.

### 8.4 Cenário conservador (renda variável)

```
renda_cons = renda_liquida × fator_renda        (padrão 0.80)
desp_cons  = piso_essencial × fator_despesa     (padrão 1.10)
B_cons = max(0, renda_cons − desp_cons − outras_despesas × fator_despesa)
```

Exibir base vs conservador. O plano oficial usa o cenário escolhido pelo usuário;
o conservador é recomendado para renda variável.

### 8.5 Aplicação do cenário

- Simulação **não altera** dados reais.
- "Aplicar" cria novo plano com `input_snapshot` ajustado e arquiva o anterior.
- Registrar origem (`simulation_id`) e `engine_version`.

---

## 9. Avisos e classificação de risco

| Código | Condição | Severidade | Mensagem |
|--------|----------|------------|----------|
| `W_BUDGET_NEGATIVE` | `B <= 0` | crítico | Orçamento para dívidas é zero/negativo |
| `W_MIN_EXCEEDS_BUDGET` | `M > B` | crítico | Mínimos não cabem no orçamento |
| `W_NEGATIVE_AMORT` | `mínimo <= saldo × i` | crítico | Dívida cresce com o mínimo |
| `W_AGGREGATE_GROWTH` | saldo total sobe por 3 meses | crítico | Dívida total crescendo |
| `W_LONG_PLAN` | `meses > 60` | alerta | Prazo longo; considere renegociar |
| `W_NO_EMERGENCY` | sem reserva e dívida cara | alerta | Considere reserva mínima |
| `W_LOCKED_DEBT` | dívida travada | info | Ordem manual pode custar juros |
| `W_RATE_ESTIMATED` | taxa estimada | info | Confirme a taxa com o credor |
| `W_CET_MISSING` | sem CET | info | CET ajuda a comparar custo real |
| `W_PLAN_STALE` | dados mudaram | info | Recalcule o plano |

**Bloqueios:** `B <= 0` e `M > B` impedem geração de calendário; retornar
`inviavel` com `infeasible_reason`.

---

## 10. Validação e erros

| Validação | Erro |
|-----------|------|
| Renda > 0 | `renda_invalida` |
| Saldo ≥ 0 | `saldo_invalido` |
| Taxa entre 0 e 1 | `taxa_invalida` |
| Mínimo > 0 | `minimo_invalido` |
| Ao menos 1 dívida ativa | `sem_dividas` |
| Sem valores NaN/Infinity | `valor_invalido` |
| Limite de meses ≥ 1 | `parametro_invalido` |
| Soma de mínimos > B | `inviavel` (não é exceção técnica) |

**Erros técnicos** (exceções) não devem vazar detalhes ao usuário; logar com
`request_id` e retornar mensagem amigável.

---

## 11. Estratégia de testes

### 11.1 Testes unitários (motor puro)

- Conversões de taxa (mensal ↔ anual) com tolerância de 1e-9.
- `PMT` com `i > 0` e `i = 0`.
- Taxa implícita: ida e volta (`PMT → i → PMT`).
- Ordenações e desempates.
- Viabilidade e avisos.
- Arredondamento e reconciliação de totais.
- Determinismo: executar 100 vezes e comparar hash.
- Casos de ouro da seção 6.

### 11.2 Testes de propriedade (property-based)

- `total_pago = principal_total + juros_total` (tolerância de centavos).
- Saldo nunca negativo.
- Pagamento do mês ≤ B + extras.
- Nenhum pagamento após quitação.
- Soma dos pagamentos por dívida = saldo inicial + juros da dívida.
- Reordenar dívidas de entrada não muda resultado para a mesma estratégia.

### 11.3 Testes de integração

- Plano persistido reproduz o mesmo resultado a partir do snapshot.
- Alteração de dados marca plano como `stale`.
- Pagamento recalcula e mantém histórico.
- Isolamento por usuário.
- Simulação não persiste sem "aplicar".

### 11.4 Critério de aceite

- ≥ 90% de cobertura no pacote `engine`.
- Todos os casos de ouro verdes.
- Nenhuma diferença > R$ 0,01 em relação à planilha de referência.
- Performance < 300 ms para 20 dívidas × 60 meses.

---

## 12. Versionamento do motor

- `engine_version` inteiro, incrementado a cada mudança que altere resultados.
- Planos guardam a versão usada; nunca recalcular plano histórico silenciosamente.
- Mudanças incompatíveis exigem migração/recálculo explícito com aviso ao usuário.
- Changelog do motor em `Docs/` ou no repositório (`CHANGELOG-engine.md`).

**Exemplos de mudança que exige versão:** arredondamento, ordem de abatimento,
critério de quick win, tratamento de aporte extra.

**Mudanças que não exigem:** textos, formatação, novos campos opcionais que não
alteram cálculo.

---

## 13. Limitações e premissas

1. Taxas são **constantes** no tempo (sem indexadores como IPCA/Selic).
2. Não modela IOF, tarifas, seguros ou encargos de atraso além da taxa informada.
3. Não modela feriados/vencimentos em fim de semana (competência mensal).
4. Não considera inflação nem rendimento de reserva.
5. Não prevê renda futura incerta; cenário conservador é heurística.
6. Pagamentos são tratados como mensais; aportes extras são por competência.
7. Não substitui cálculo oficial do credor; divergências devem ser corrigidas
   pelo usuário.

**Mitigação:** exibir premissas no plano e permitir ajuste de saldo/taxa.
Incluir aviso: "valores aproximados; confirme com seu credor".

---

## 14. Ética e conformidade

- **Mínimo existencial:** o motor nunca sugere pagamento que o viole.
- **Superendividamento:** se o plano for inviável ou > 5 anos, sugerir
  renegociação e informar sobre a Lei nº 14.181/2021, sem prometer resultado.
- **Sem recomendação de crédito:** não sugerir contratar empréstimo para pagar
  dívida; apenas simular cenários fornecidos pelo usuário.
- **Transparência:** mostrar juros, premissas, custo das escolhas e avisos.
- **Linguagem:** acolhedora, sem culpa; foco em próximo passo.
- **Disclaimer:** visível no plano e nos relatórios exportados.

---

## 15. Integração com o restante do sistema

| Consumidor | Como usa |
|------------|----------|
| `PlanService` | Monta `PlanInput`, chama motor, persiste snapshot |
| `SimulationService` | Chama motor com parâmetros ajustados, sem persistir dívidas |
| Dashboard | Exibe `saldo_livre`, `comprometimento`, próximo pagamento |
| API | Endpoints `/plans`, `/simulations` |
| Relatórios | Consome `plan_schedules` persistidos |
| Testes | Importa o pacote `engine` diretamente |

---

## 16. Pseudocódigo de referência (Python)

```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)

def monthly_rate_from_annual(annual: Decimal) -> Decimal:
    return (Decimal(1) + annual) ** (Decimal(1) / Decimal(12)) - Decimal(1)

def pmt(principal: Decimal, rate: Decimal, n: int) -> Decimal:
    if rate == 0:
        return principal / n
    factor = (Decimal(1) + rate) ** (-n)
    return principal * rate / (Decimal(1) - factor)

def order_debts(debts, strategy, surplus, total):
    locked = sorted([d for d in debts if d.locked], key=lambda d: d.locked)
    unlocked = [d for d in debts if not d.locked]

    avalanche_key = lambda d: (-d.monthly_rate, d.balance, d.due_day, d.id)
    snowball_key = lambda d: (d.balance, -d.monthly_rate, d.due_day, d.id)

    if strategy == "avalanche":
        ordered = sorted(unlocked, key=avalanche_key)
    elif strategy == "snowball":
        ordered = sorted(unlocked, key=snowball_key)
    elif strategy == "hybrid":
        quick = [
            d for d in unlocked
            if d.balance <= 2 * max(surplus, 0) or d.balance <= Decimal("0.10") * total
        ]
        quick_ids = {d.id for d in quick}
        quick_sorted = sorted(quick, key=snowball_key)
        rest_sorted = sorted(
            [d for d in unlocked if d.id not in quick_ids],
            key=avalanche_key,
        )
        ordered = quick_sorted + rest_sorted
    else:
        raise ValueError("strategy")

    return locked + ordered

def simulate(B: Decimal, debts, strategy, start_month, extra=Decimal(0),
             extra_months=0, max_months=600):
    # ... implementação conforme seção 5 ...
```

> O código de produção deve adicionar tipos, validações, logs de aviso e testes.
> O pacote `engine` não importa Django.

---

## 17. Checklist de implementação

- [ ] Motor puro, sem dependência de Django/DB.
- [ ] Conversões de taxa com testes de ida e volta.
- [ ] `B` vs `S` claramente separados.
- [ ] Viabilidade e avisos implementados.
- [ ] Ordenações determinísticas e documentadas.
- [ ] Rollover embutido e testado.
- [ ] Arredondamento consistente e reconciliação.
- [ ] Limite de 600 meses e `prazo_excedido`.
- [ ] Snapshot + `engine_version`.
- [ ] Casos de ouro verdes.
- [ ] Comparação de estratégias e recomendação.
- [ ] Cenários (corte, extra, renegociação, conservador).
- [ ] Avisos éticos e disclaimer.
- [ ] Performance medida e aceitável.
