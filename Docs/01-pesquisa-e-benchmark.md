# 01 — Pesquisa, Benchmark e Fundamentos

**Objetivo:** fundamentar as decisões do produto com práticas reconhecidas de
orçamento, quitação de dívidas, indicadores de risco, contexto regulatório
brasileiro e análise de concorrentes.

**Data:** 2026-11-19
**Método:** pesquisa secundária (fontes públicas), análise comparativa e síntese
para o contexto do produto. Não houve entrevistas primárias nesta rodada; o
[plano de validação](#8-plano-de-validação-com-usuários) está no final.

---

## 1. Principais conclusões (TL;DR)

1. **Não existe um método único ideal.** A literatura aponta que a escolha entre
   avalanche e snowball envolve matemática **e** comportamento. O produto deve
   oferecer ambos e uma opção híbrida, com recomendação explicada.
2. **Snowball tem vantagem comportamental.** Estudos citados pela literatura
   indicam que quitar saldos pequenos primeiro aumenta a percepção de progresso
   e a chance de eliminação total da dívida, mesmo custando mais juros.
3. **Avalanche é financeiramente ótima.** Priorizar a maior taxa reduz juros
   totais, desde que o usuário mantenha o plano.
4. **Orçamento precisa ser realista.** Métodos como 50/30/20, envelope,
   zero-based e kakeibo funcionam, mas exigem separar **essencial** de
   **discricionário**. O app deve fazer essa distinção sem fricção.
5. **DTI e taxa de comprometimento são bússolas.** Comprometimento acima de
   ~30% da renda já merece atenção; acima de ~50% é crítico.
6. **Mínimo existencial é requisito legal e ético.** A Lei nº 14.181/2021
   exige preservá-lo em planos de repactuação; o produto deve torná-lo explícito.
7. **Open Finance é oportunidade futura, não pré-requisito.** O MVP entrega
   valor com entrada manual e importação de arquivos.
8. **A maior barreira é fricção, não falta de funcionalidade.** Onboarding
   guiado e lançamento rápido valem mais que dezenas de gráficos.

---

## 2. Métodos de orçamento pessoal

### 2.1 50/30/20

Divide a renda líquida em:

- **50% necessidades** (moradia, alimentação, transporte, saúde, utilities);
- **30% desejos** (lazer, streaming, restaurantes, compras não essenciais);
- **20% poupança e pagamento de dívidas.**

**Uso no produto:** diagnóstico inicial e sugestão de meta. Em situação de
endividamento, a fatia de 20% pode ser realocada temporariamente para quitação,
com aviso de que a reserva de emergência não deve ser ignorada por completo.

**Limitação:** não funciona bem para rendas muito baixas ou variáveis; precisa
de adaptação por faixa de renda.

### 2.2 Pay yourself first (80/20)

Separa primeiro a poupança (ou o pagamento de dívidas) e só depois gasta o
restante. Variações: 70/30, 60/40, 50/50.

**Uso no produto:** permitir definir um "valor sagrado" mensal para dívidas,
debitado mentalmente antes das despesas discricionárias.

### 2.3 Envelope (cash-only)

Cada categoria recebe um envelope com valor fixo; quando acaba, não se gasta mais.

**Uso no produto:** orçamento por categoria com "envelopes digitais" e alerta ao
atingir 80%/100%. No MVP, pode ser um relatório simples em vez de bloqueio.

### 2.4 Zero-based budgeting

Todo real recebe um destino antes do mês começar; o saldo do orçamento termina em zero.

**Uso no produto:** modo avançado (P1) para usuários que querem controle granular.
No MVP, o conceito entra no cálculo do saldo livre: renda − essenciais − dívidas − metas = 0.

### 2.5 Kakeibo

Método japonês de registro consciente: anotar gastos, revisar semanalmente e
refletir sobre escolhas, dividindo despesas em necessidades, desejos, cultura e
imprevistos.

**Uso no produto:** tom educativo, revisão semanal e perguntas de reflexão;
gamificação leve baseada em consistência, não em punição.

### 2.6 Qual método recomendar?

| Perfil | Método sugerido | Motivo |
|--------|-----------------|--------|
| Iniciante, renda fixa | 50/30/20 adaptado | Simples e visual |
| Endividado, renda baixa | Orçamento de essenciais + mínimo existencial | Evita plano inviável |
| Renda variável | Média de 3–6 meses + cenário conservador | Reduz risco de default |
| Controlador nato | Zero-based | Máximo controle |
| Quem quer simplicidade | Pay yourself first | Menos categorização |

**Decisão de produto:** o app **não impõe** um método; ele **diagnostica** o
perfil e sugere um caminho, sempre permitindo trocar.

---

## 3. Métodos de quitação de dívidas

### 3.1 Debt Avalanche (avalanche)

**Regra:** pagar o mínimo em todas as dívidas e direcionar o excedente para a
dívida com **maior taxa de juros**. Quando quitada, o valor liberado (mínimo +
excedente) é somado ao pagamento da próxima.

**Prós:** minimiza juros totais e tende a reduzir o prazo.
**Contras:** a primeira vitória pode demorar; exige disciplina.
**Indicado para:** quem é analítico, tem dívidas com taxas muito distintas e
tolera recompensa tardia.

### 3.2 Debt Snowball (bola de neve)

**Regra:** ordenar por **menor saldo** e atacar a primeira, pagando o mínimo nas
demais. Ao quitar, o valor é rolado para a próxima.

**Prós:** vitórias rápidas, reduz o número de contas, aumenta motivação.
**Contras:** pode custar mais juros se as dívidas pequenas forem baratas e as
grandes caras.
**Indicado para:** quem precisa de reforço comportamental e tem muitas dívidas
pequenas.

### 3.3 Evidências e nuance

A literatura (estudos citados na página da Wikipedia sobre snowball) indica que:

- consumidores que atacam saldos pequenos primeiro têm maior probabilidade de
  eliminar a dívida total;
- a percepção de progresso depende mais da **proporção** do saldo paga do que do
  valor absoluto;
- quando confrontados com o custo de juros, alguns consumidores mudam para a
  decisão matematicamente ótima;
- não há método ideal universal: traços de personalidade e contexto importam.

**Implicação direta:** oferecer os dois métodos, mostrar o custo da escolha e
deixar o usuário decidir com transparência.

### 3.4 Híbrido (recomendação do produto)

Combina o melhor dos dois:

1. **Fase 1 — Quick wins:** quitar dívidas cujo saldo seja pequeno em relação ao
   orçamento livre (ex.: ≤ 2 meses de excedente) ou que representem ≤ 10% da
   dívida total. Isso reduz o número de credores e gera momentum.
2. **Fase 2 — Avalanche:** a partir daí, priorizar a maior taxa efetiva.

**Parâmetros configuráveis:** limite de quick wins, ordem de desempate e
possibilidade de "travar" uma dívida (ex.: não atrasar o financiamento da casa).

### 3.5 Consolidação e renegociação

- **Consolidação:** trocar várias dívidas por uma, geralmente com juros menores e
  prazo maior. Requer cuidado com CET, garantias e custo total.
- **Renegociação:** negociar desconto, prazo ou juros. O app pode simular o
  impacto de uma proposta e sugerir um valor máximo sustentável.
- **Superendividamento:** quando a renda não cobre o mínimo existencial, pode
  caber o processo de repactuação da Lei nº 14.181/2021 (plano de até 5 anos).

**Uso no produto:** simulador com campos "nova taxa", "novo prazo" e "desconto";
comparação entre manter e renegociar. Não intermediar acordos.

---

## 4. Indicadores de saúde financeira

### 4.1 Taxa de comprometimento da renda

```
comprometimento = (soma das parcelas mensais de dívidas ÷ renda líquida mensal) × 100
```

| Faixa | Leitura | Ação sugerida |
|-------|---------|---------------|
| ≤ 20% | Saudável | Manter e poupar |
| 20–30% | Atenção | Evitar novas dívidas |
| 30–50% | Alerta | Priorizar quitação e cortar supérfluos |
| > 50% | Crítico | Plano agressivo, renegociação, apoio profissional |

### 4.2 DTI (Debt-to-Income)

Percentual da renda comprometido com dívidas. Duas leituras comuns:

- **front-end:** custos de moradia;
- **back-end:** todas as dívidas recorrentes.

No produto, usar a leitura **back-end** simplificada:
`DTI = parcelas mensais de dívidas / renda bruta mensal`.
Exibir também a versão sobre renda líquida, que é mais conservadora.

### 4.3 Saldo livre real

```
saldo_livre = renda_líquida
            − despesas_essenciais
            − mínimo_existencial_já_contido_nas_essenciais (evitar dupla contagem)
            − parcelas_mínimas_das_dívidas
            − reserva_de_segurança_opcional
```

**Decisão:** o mínimo existencial é um **piso**, não um valor somado cegamente.
Se as despesas essenciais já o cobrem, não somar de novo. O app deve mostrar a
memória de cálculo.

### 4.4 Reserva de emergência

Recomendação usual: 3–6 meses de despesas essenciais. Em contexto de dívida cara,
o trade-off é:

- **Primeiro:** reserva mínima de 1 mês (evita novo endividamento por imprevisto);
- **Depois:** priorizar dívidas com juros acima do rendimento da reserva.

O app pode tratar a reserva como "despesa planejada" ou como meta separada (P1).

### 4.5 Outros indicadores úteis

- **Juros pagos no mês:** quanto do pagamento virou juros, não principal.
- **Número de credores:** menos credores = menos risco operacional.
- **Tempo até quitação:** meses restantes no cenário atual vs. plano.
- **Juros economizados:** diferença entre cenário atual e plano escolhido.
- **Índice de esforço:** parcela mínima total ÷ renda.

---

## 5. Contexto regulatório e de mercado no Brasil

### 5.1 Lei nº 14.181/2021 (superendividamento)

Pontos relevantes:

- Define superendividamento como impossibilidade manifesta de pagar todas as
  dívidas de consumo, exigíveis e vincendas, **sem comprometer o mínimo existencial**.
- Exige preservação do mínimo existencial na repactuação e na concessão de crédito.
- Prevê plano de pagamento com prazo máximo de **5 anos** em processo de repactuação.
- Reforça deveres de informação (CET, taxa efetiva, consequências do inadimplemento).
- Exclui dívidas com garantia real, financiamento imobiliário e crédito rural do
  processo de repactuação; também afasta casos de má-fé/fraude.

**Implicações para o produto:**

- O conceito de mínimo existencial deve ser explícito no onboarding e no motor.
- Planos devem alertar quando o prazo estimado excede 5 anos e sugerir renegociação.
- O app deve informar que não substitui orientação jurídica.
- O simulador pode comparar "plano atual" vs. "plano de repactuação" como
  exercício educativo, sem prometer resultado.

### 5.2 Open Finance

- O Brasil estruturou um dos maiores ecossistemas de Open Finance do mundo.
- Fases incluíram dados cadastrais, transações, cartões, crédito e iniciação de
  pagamento, com consentimento do cliente.
- Benefício potencial: reduzir fricção de entrada e melhorar diagnóstico.
- Riscos: consentimento, segurança, privacidade, disponibilidade e complexidade
  regulatória.

**Decisão:** Open Finance fica para **P2**. O MVP usa entrada manual + CSV/OFX (P1).
A arquitetura deve prever um `ImportSource`/`Connection` desacoplado.

### 5.3 LGPD

- Dados financeiros são dados pessoais e exigem base legal, finalidade,
  minimização, segurança e transparência.
- Direitos do titular: confirmação, acesso, correção, anonimização/bloqueio,
  portabilidade, eliminação, informação sobre compartilhamento.
- Self-hosted não isenta o operador de responsabilidades.

Detalhes em [08-seguranca-e-lgpd.md](08-seguranca-e-lgpd.md).

---

## 6. Benchmark de concorrentes e referências

> Análise qualitativa de posicionamento, baseada em conhecimento público.
> Funcionalidades específicas devem ser validadas antes de decisões de roadmap.

| Produto | Proposta | Pontos fortes | Lacunas para o nosso caso |
|---------|----------|---------------|---------------------------|
| **YNAB** | Orçamento por envelope, zero-based | Metodologia forte, educação, comunidade | Curva de aprendizado, foco em orçamento e não em plano de dívida |
| **Mobills** | Gestão financeira pessoal | App maduro, categorias, relatórios | Pouca prescrição de quitação; importação como centro |
| **Organizze** | Controle financeiro | Simplicidade, relatórios, uso BR | Plano de dívida limitado |
| **GuiaBolso** (encerrado) | Agregador bancário | Visão consolidada, categorização automática | Dependência de agregadores; não resolvia a decisão |
| **Apps de banco** (Nubank, Itaú etc.) | Extrato e cartão | Dados completos, baixa fricção | Visão fragmentada entre instituições; sem plano multi-credor |
| **Serasa / birôs** | Negociação e score | Base de credores, acordos | Não calcula capacidade sustentável; foco em desconto |
| **Planilhas/consultores** | Personalização total | Flexibilidade | Manual, caro, não escala |

### 6.1 Matriz de capacidades

| Capacidade | YNAB | Mobills | Organizze | Bancos | Serasa | Clareza (MVP) |
|------------|------|---------|-----------|--------|--------|---------------|
| Controle de receitas/despesas | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ |
| Orçamento por categoria | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ (P1) |
| Cadastro de dívidas | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ordem de quitação | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| Calendário de pagamento | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| Comparação de estratégias | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| Simulação de cenários | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| Mínimo existencial | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| Importação automática | ✅ | ✅ | ✅ | ✅ | ➖ | P1/P2 |
| Self-hosted/privacidade | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |

Legenda: ✅ presente; ➖ ausente ou limitado; P1/P2 planejado.

### 6.2 Lições de UX

1. **Onboarding curto vence.** Apps que pedem muitos dados antes do primeiro valor
   perdem usuários. Regra: valor em < 10 minutos.
2. **Categorização automática reduz fricção.** Sem ela, oferecer templates e
   categorias sugeridas.
3. **Notificações úteis, não spam.** Um lembrete no vencimento vale mais que
   dez alertas genéricos.
4. **Progresso visível.** Barras de dívida quitada e "juros economizados" são
   motivadores poderosos.
5. **Linguagem sem culpa.** Evitar "você gastou demais"; usar "essa categoria
   ficou acima do planejado; quer ajustar?".
6. **Transparência.** Explicar cálculos e premissas evita desconfiança.

---

## 7. Oportunidades para o produto

| # | Oportunidade | Evidência | Esforço | Impacto |
|---|--------------|-----------|---------|---------|
| O1 | Plano de quitação explicável | Lacuna dos concorrentes | M | Alto |
| O2 | Híbrido configurável | Literatura mostra trade-offs | M | Alto |
| O3 | Simulador de cenários | Decisão é o gargalo | M | Alto |
| O4 | Mínimo existencial explícito | Lei 14.181 + ética | S | Alto |
| O5 | Onboarding com renda variável | Autônomos são parcela relevante | M | Médio |
| O6 | Importação CSV/OFX | Reduz fricção | M | Médio |
| O7 | Multiusuário familiar | Casais compartilham dívidas | L | Médio |
| O8 | Educação contextual | Aumenta adesão | S | Médio |
| O9 | Open Finance | Menos fricção no futuro | XL | Alto (longo prazo) |
| O10 | Alertas preditivos de risco | Evita recaída | M | Médio |

---

## 8. Plano de validação com usuários

Antes de investir em P1/P2, validar com 10–15 entrevistas:

**Roteiro (30 min):**

1. Conte como você organiza suas finanças hoje. (contexto)
2. Qual foi a última vez que você decidiu qual dívida pagar? O que fez? (comportamento passado)
3. O que te impede de pagar mais? (barreiras)
4. Como você descobre a taxa real das suas dívidas? (informação)
5. O que você faria com um plano que dissesse "pague X nesta dívida"? (reação)
6. Você confiaria em um app self-hosted? Por quê? (confiança)
7. O que faria você abandonar o app? (retenção)

**Hipóteses a testar:**

- H1: usuários preferem uma recomendação pronta a comparar estratégias sozinhos.
- H2: ver "juros economizados" aumenta intenção de seguir o plano.
- H3: mínimo existencial explícito aumenta confiança e reduz vergonha.
- H4: lançamento manual é aceitável se o onboarding entregar valor rápido.
- H5: privacidade/self-hosted é diferencial para um nicho, não para todos.

**Critérios de continuar:** ≥ 7 de 10 entrevistados relatam a dor de "não saber
o que pagar primeiro" e ≥ 5 demonstram intenção de usar o protótipo.

---

## 9. Referências

1. **Lei nº 14.181/2021** — Planalto.
   <https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/L14181.htm>
2. **Debt snowball method** — Wikipedia.
   <https://en.wikipedia.org/wiki/Debt_snowball_method>
3. **Personal budget** — Wikipedia (50/30/20, envelope, zero-based, kakeibo).
   <https://en.wikipedia.org/wiki/Personal_budget>
4. **Debt-to-income ratio** — Wikipedia.
   <https://en.wikipedia.org/wiki/Debt-to-income_ratio>
5. **Open banking** — Wikipedia (inclui histórico e fases do Brasil).
   <https://en.wikipedia.org/wiki/Open_banking>
6. **Banco Central do Brasil** — Open Finance (documentação oficial).
   <https://www.bcb.gov.br/estabilidadefinanceira/openfinance>
7. **ANPD** — Lei Geral de Proteção de Dados (orientações).
   <https://www.gov.br/anpd/pt-br>

> Observação: fontes como Investopedia e CFPB bloquearam acesso automatizado
> durante a pesquisa; os conceitos foram validados pelas fontes acima e por
> conhecimento consolidado de domínio.
