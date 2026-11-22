# Clareza Financeira — Documentação do Produto

> Aplicativo de gestão financeira pessoal com foco em **regularização de dívidas**:
> registra receitas, despesas e dívidas e gera um **plano de pagamento acionável**
> a partir da capacidade real de pagamento do usuário.

**Status:** Fase 4 implementada / beta operacional pronto para iniciar
**Versão:** 0.1.0
**Última atualização:** 2026-11-19

---

## 1. Sobre este diretório

Toda a documentação de produto, negócio, arquitetura e operação vive em `Docs/`.
O código da aplicação ficará na raiz do repositório (Django + Docker).

Para subir o ambiente: veja o [Runbook](13-runbook.md).
O progresso da execução está em [12-plano-de-execucao.md](12-plano-de-execucao.md).

O objetivo desta documentação é permitir que qualquer pessoa (ou agente de IA)
consiga:

1. Entender **por que** o produto existe e para quem.
2. Saber **o que** será construído e o que está fora de escopo.
3. Entender **como** o motor de regularização calcula o plano.
4. Implementar, testar e operar o sistema sem depender de conhecimento tribal.

---

## 2. Índice

| # | Documento | Conteúdo | Público-alvo |
|---|-----------|----------|--------------|
| 00 | [PRD.md](PRD.md) | Documento de requisitos de produto: problema, solução, escopo, métricas, riscos e cronograma | Todos |
| 01 | [01-pesquisa-e-benchmark.md](01-pesquisa-e-benchmark.md) | Pesquisa de mercado, benchmarks, métodos de orçamento e quitação, referências | Produto / Negócio |
| 02 | [02-personas-e-jornadas.md](02-personas-e-jornadas.md) | Personas, Jobs-to-be-Done, jornadas e mapa de histórias | Produto / Design |
| 03 | [03-requisitos-e-regras-de-negocio.md](03-requisitos-e-regras-de-negocio.md) | Requisitos funcionais e não funcionais, regras de negócio e critérios de aceite | Produto / Engenharia / QA |
| 04 | [04-arquitetura-tecnica.md](04-arquitetura-tecnica.md) | Arquitetura Django/Docker/PostgreSQL, ambientes, deploy, observabilidade | Engenharia / DevOps |
| 05 | [05-modelo-de-dados.md](05-modelo-de-dados.md) | Modelo ER, tabelas, campos, índices, constraints e convenções | Engenharia |
| 06 | [06-motor-plano-regularizacao.md](06-motor-plano-regularizacao.md) | Algoritmos avalanche/snowball/híbrido, fórmulas, pseudocódigo e casos de borda | Produto / Engenharia |
| 07 | [07-api-e-integracoes.md](07-api-e-integracoes.md) | Contratos REST, autenticação, paginação, erros e roadmap de integrações | Engenharia |
| 08 | [08-seguranca-e-lgpd.md](08-seguranca-e-lgpd.md) | Modelo de ameaças, controles, LGPD, retenção, backup e resposta a incidentes | Engenharia / Security |
| 09 | [09-roadmap-backlog-e-riscos.md](09-roadmap-backlog-e-riscos.md) | Fases, backlog priorizado (RICE/MoSCoW), riscos e definição de pronto | Produto / Engenharia |
| 10 | [10-adr-decisoes-arquiteturais.md](10-adr-decisoes-arquiteturais.md) | Registro das decisões arquiteturais (ADRs) | Engenharia |
| 11 | [11-design-system-material-glass.md](11-design-system-material-glass.md) | Design system: Material Design 3 + Glassmorphism, tokens, componentes, acessibilidade e implementação | Produto / Design / Engenharia |
| 12 | [12-plano-de-execucao.md](12-plano-de-execucao.md) | Plano de execução, fases, tarefas, quality gates e status | Todos |
| 13 | [13-runbook.md](13-runbook.md) | Runbook de desenvolvimento, deploy, backup, restore e troubleshooting | Engenharia / DevOps |
| 14 | [14-importacao-de-extratos.md](14-importacao-de-extratos.md) | Importação de extratos OFX: passo a passo funcional e técnico, categorização assistida e deduplicação | Produto / Engenharia |

---

## 3. Resumo em uma página

**Problema.** Muitas pessoas conseguem registrar gastos, mas não sabem *qual dívida
pagar primeiro* nem *quanto podem pagar sem comprometer o essencial*. Planilhas e
apps de orçamento mostram o passado; falta uma recomendação prescritiva e simulações
de futuro.

**Solução.** Um app self-hosted (Docker + Django + PostgreSQL) que:

- Centraliza receitas, despesas e dívidas por usuário.
- Calcula indicadores de saúde financeira (saldo livre, taxa de comprometimento, DTI).
- Gera um **plano de regularização** com ordem de pagamento, calendário mês a mês,
  juros projetados e data estimada de quitação.
- Permite comparar estratégias (**avalanche**, **snowball** e **híbrida**) e simular
  cenários ("e se eu cortar R$ 300?" ou "e se eu conseguir R$ 500 extras?").
- Respeita o **mínimo existencial**, alinhado à Lei nº 14.181/2021.

**Diferencial.** Não é mais um rastreador de gastos: é um **copiloto de quitação**
que transforma números em um próximo passo concreto.

**Nome de trabalho.** *Clareza Financeira* (alternativas: *Quita*, *Dívida Zero*,
*Farol Financeiro*). Nome definitivo é decisão de marca, não bloqueia o MVP.

---

## 4. Convenções da documentação

- **Idioma:** português do Brasil (pt-BR).
- **Moeda:** BRL por padrão; modelo preparado para `currency` por perfil.
- **Valores monetários:** `Decimal` com 2 casas; nunca `float`.
- **Taxas:** armazenadas como fração decimal mensal (ex.: `0.0199` = 1,99% a.m.)
  e exibidas como percentual. Conversão anual ↔ mensal documentada no motor.
- **Datas:** ISO-8601 (`YYYY-MM-DD`), fuso `America/Sao_Paulo`.
- **IDs:** UUID v4 nas entidades de negócio.
- **Versionamento:** SemVer para a documentação; toda mudança relevante gera ADR.
- **Diagramas:** Mermaid (renderiza no GitHub/GitLab e em editores compatíveis).

---

## 5. Glossário rápido

| Termo | Definição |
|-------|-----------|
| **Mínimo existencial** | Valor mínimo necessário para necessidades básicas (moradia, alimentação, saúde, transporte etc.), preservado em planos de repactuação. |
| **DTI** | *Debt-to-Income ratio*: percentual da renda comprometido com dívidas. |
| **Taxa de comprometimento** | Soma das parcelas mensais de dívidas ÷ renda líquida mensal. |
| **Avalanche** | Pagar primeiro a dívida de **maior juros**, maximizando economia. |
| **Snowball (bola de neve)** | Pagar primeiro a dívida de **menor saldo**, gerando vitórias rápidas. |
| **Híbrido** | Combina quick wins (snowball limitado) com avalanche para o restante. |
| **Saldo livre** | Renda líquida − despesas essenciais − mínimo existencial − parcelas mínimas das dívidas. |
| **Snowball effect** | Reaproveitar a parcela de uma dívida quitada para acelerar a próxima. |
| **CET** | Custo Efetivo Total de uma operação de crédito. |
| **Superendividamento** | Impossibilidade manifesta de pagar todas as dívidas de consumo sem comprometer o mínimo existencial (Lei 14.181/2021). |

---

## 6. Princípios de produto

1. **Ação antes de análise.** Todo número deve levar a uma decisão ou próximo passo.
2. **Verdade desconfortável, mas clara.** Se o plano não fecha, o app diz isso.
3. **O essencial é intocável.** Nenhum plano sugere comprometer o mínimo existencial.
4. **Privacidade por padrão.** Self-hosted, sem venda de dados, exportação e exclusão fáceis.
5. **Simplicidade operacional.** Um `docker compose up` deve subir o sistema completo.
6. **Explicabilidade.** O usuário entende *por que* aquela dívida ficou em primeiro lugar.
7. **Educação, não julgamento.** Linguagem acolhedora, sem culpa ou gamificação agressiva.
8. **Identidade visual:** Material Design 3 como UX e Glassmorphism como camada de
   destaque, sem sacrificar contraste, legibilidade ou performance.

---

## 7. Próximos passos sugeridos

1. **Validar** as personas e o roteiro de entrevistas (doc 01, seção 8) com 10–15 pessoas.
2. **Fechar** as decisões pendentes: nome, MFA, importação OFX, workspace familiar.
3. **Revisar** as fórmulas do motor com um especialista financeiro (doc 06).
4. **Prototipar** as telas de onboarding, plano e simulador (baixa fidelidade).
5. **Fase 1 concluída:** Docker, Django, auth, perfil, design base, testes e CI.
6. **Fase 2 concluída:** categorias, contas, transações, parcelamento, recorrência, dívidas, pagamentos e dashboard real.
7. **Fase 3 concluída:** motor avalanche/snowball/híbrida, plano, calendário, comparação e simulador.
8. **Fase 4 implementada:** aderência, relatórios, exportação, notificações, LGPD e hardening.
9. **Iniciar o beta fechado:** `seed_demo`, 10–20 usuários, feedback e pentest externo.
10. **Antes do beta público:** política de privacidade, pentest, backup testado e RIPD.

> Enquanto as decisões não fecham, use o nome de trabalho *Clareza Financeira*.

---

## 8. Como manter

- Alterou escopo? Atualize `PRD.md` **e** `03-requisitos-e-regras-de-negocio.md`.
- Alterou cálculo? Atualize `06-motor-plano-regularizacao.md` e adicione testes de regressão.
- Alterou a interface? Atualize `11-design-system-material-glass.md` e os tokens.
- Tomou decisão estrutural? Crie um ADR em `10-adr-decisoes-arquiteturais.md`.
- Antes de codar, leia `PRD.md`, `03-requisitos...`, `04-arquitetura...` e `11-design...`.

---

> **Aviso legal:** o produto oferece organização financeira e simulações educativas.
> Não constitui consultoria de investimentos, recomendação de crédito ou assessoria
> jurídica. Casos de superendividamento devem ser avaliados por profissional habilitado
> e podem ser tratados nos termos da Lei nº 14.181/2021.
