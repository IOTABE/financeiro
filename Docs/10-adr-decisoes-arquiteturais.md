# 10 — Registro de Decisões Arquiteturais (ADRs)

**Formato:** Contexto → Decisão → Alternativas → Consequências → Status.
**Status possíveis:** Proposto · Aceito · Substituído · Descontinuado.

---

## ADR-001 — Stack Django + PostgreSQL + Docker

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** O solicitante definiu Docker, Django e PostgreSQL. O produto é um
monólito web com cálculos financeiros, autenticação, CRUD e projeções; a equipe
é pequena e a operação deve ser simples e self-hosted.

**Decisão.** Usar Python 3.12+, Django 5.x, PostgreSQL 16, Docker Compose,
Gunicorn e Nginx.

**Alternativas.** FastAPI + React; Flask + SQLAlchemy; Node/NestJS + PostgreSQL.

**Consequências.**

- (+) Batteries included: auth, admin, ORM, migrations, segurança madura.
- (+) Ecossistema e contratação fáceis; deploy reproduzível.
- (−) Menos flexível que um SPA dedicado; admin exige hardening.
- (−) Performance de ORM exige cuidado com N+1.

---

## ADR-002 — Monólito modular

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** O escopo é coeso e a equipe é pequena. Microsserviços adicionariam
latência, complexidade operacional e custo sem benefício no MVP.

**Decisão.** Monólito Django com apps por domínio (`accounts`, `finance`, `debts`,
`plans`, `simulations`, `reports`, `notifications`, `audit`), fronteiras via
services/selectors e sem importações cruzadas indevidas.

**Alternativas.** Microsserviços; monólito em camadas único.

**Consequências.**

- (+) Simplicidade de deploy, transações ACID e debugging.
- (+) Refatoração para serviços é possível se necessário.
- (−) Disciplina de fronteiras precisa ser mantida em code review.
- (−) Um deploy afeta todo o sistema.

---

## ADR-003 — UI server-rendered com HTMX + Material 3 + Tailwind

**Status:** Aceito · **Data:** 2026-11-19 · **Atualizado:** 2026-11-19

**Contexto.** O público é mobile-first, mas o MVP precisa entregar rápido com
pouca complexidade de frontend. A API será necessária para um futuro app.
A direção visual definida é Material UX + Glassmorphism.

**Decisão.** Templates Django + HTMX + Alpine.js, **Material Design 3** via
`@material/web`, Tailwind CSS para layout/utilitários e uma camada CSS de tokens
de Glassmorphism. DRF expõe `/api/v1` para integrações e futuro mobile.

**Alternativas.** SPA React com MUI; Django + Bootstrap sem JS; UI kit genérico.

**Consequências.**

- (+) Menos JS, SEO, entrega rápida, menos estado no cliente.
- (+) API-first permite evoluir para SPA/mobile.
- (+) Material 3 entrega componentes acessíveis e consistentes.
- (+) Vidro com fallback preserva contraste e performance.
- (−) Interações muito ricas exigem mais HTMX/JS.
- (−) Time precisa conhecer HTMX e Material Web.
- (−) `backdrop-filter` exige disciplina de performance.
- (−) Se houver migração para MUI/React, este ADR deve ser substituído.

---

## ADR-004 — Dinheiro em Decimal, nunca float

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Cálculos financeiros exigem exatidão; `float` introduz erros de
representação e divergências de centavos.

**Decisão.** `NUMERIC(14,2)` no PostgreSQL e `Decimal` no Python, com contexto
≥ 28 dígitos. Arredondamento **half-up** a cada mês; quantização explícita.
Nunca usar `float` em domínio financeiro.

**Alternativas.** Inteiros em centavos; float com tolerância.

**Consequências.**

- (+) Resultados reproduzíveis e reconciliáveis.
- (+) Compatível com relatórios e exportação.
- (−) Mais verboso; requer disciplina em serializers/API (string decimal).
- (−) Conversões exigem atenção (ex.: taxas).

---

## ADR-005 — UUID como chave primária

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** IDs sequenciais facilitam enumeração e vazamento de volume de dados;
integrações futuras podem exigir identificadores estáveis.

**Decisão.** UUID v4 nas entidades de negócio. `plan_schedules` e `audit_logs`
usam `BIGSERIAL` por volume.

**Alternativas.** BigInt auto-incremento; ULID.

**Consequências.**

- (+) Não enumerável; seguro para URLs e APIs.
- (+) Facilita merge/exportação.
- (−) Índices maiores; leve custo de storage.
- (−) Legibilidade menor em suporte (mitigado por short IDs na UI).

---

## ADR-006 — Motor de cálculo puro, determinístico e versionado

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** O plano é o núcleo do valor. Ele precisa ser confiável, testável,
explicável e reproduzível ao longo do tempo.

**Decisão.** Pacote `apps/plans/engine/` sem dependência de Django, com tipos
imutáveis, funções puras, `Decimal`, `engine_version` e testes de propriedade e
casos de ouro. Serviços orquestram persistência.

**Alternativas.** Lógica nos models; cálculo on-the-fly na view; biblioteca externa.

**Consequências.**

- (+) Testável sem banco; rápido; reutilizável por CLI/API.
- (+) Mudanças controladas por versão.
- (−) Duplicação de tipos entre ORM e engine (mapeamento explícito).
- (−) Requer disciplina para não vazar lógica para views.

---

## ADR-007 — Plano persistido com snapshot de entrada

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** O usuário muda renda, dívidas e pagamentos; o histórico precisa ser
auditável e reproduzível. Recalcular silenciosamente destruiria a confiança.

**Decisão.** Persistir `plans` com `input_snapshot` (JSONB), `summary`,
`engine_version` e calendário em `plan_schedules`. Mudanças nos dados marcam o
plano como `stale`; o usuário decide recalcular. Apenas um plano `active` por
usuário (índice único parcial).

**Alternativas.** Calcular sempre; guardar apenas o último resultado.

**Consequências.**

- (+) Reprodutibilidade, auditoria e comparação histórica.
- (+) Evita mudanças silenciosas no plano.
- (−) Mais storage (mitigado por arquivamento e retenção).
- (−) Necessidade de recalcular explicitamente.

---

## ADR-008 — Soft delete + auditoria append-only

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Dados financeiros exigem histórico e recuperação; exclusões
acidentais não podem destruir evidências. A LGPD exige descarte controlado.

**Decisão.** `deleted_at` em entidades editáveis; `audit_logs` append-only com
eventos relevantes, sem valores/PII. Exclusão de conta anonimiza logs.

**Alternativas.** Hard delete; sem auditoria.

**Consequências.**

- (+) Recuperação e rastreabilidade.
- (+) Suporte a investigação e conformidade.
- (−) Consultas precisam filtrar `deleted_at`.
- (−) Retenção e expurgo exigem rotina.

---

## ADR-009 — Redis + Celery para tarefas assíncronas

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Recorrências, lembretes, recálculos e exportações não devem bloquear
requisições; o Cron do host é frágil e pouco observável.

**Decisão.** Redis 7 (cache + broker) e Celery worker/beat no Docker Compose.

**Alternativas.** Cron do host; Django-Q; fila em banco.

**Consequências.**

- (+) Retry, agendamento, observabilidade e portabilidade.
- (+) Escala horizontal do worker.
- (−) Mais um serviço para operar.
- (−) Necessidade de idempotência e monitoramento de fila.

---

## ADR-010 — Sessão para web; token para API (P1)

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** A UI é server-rendered; um futuro app mobile precisará de API.
Misturar mecanismos sem critério aumenta a superfície de ataque.

**Decisão.** Sessão Django (cookie seguro + CSRF) para web. Tokens pessoais com
escopos para API (P1); MFA TOTP opcional. Sem JWT no MVP.

**Alternativas.** JWT para tudo; apenas tokens.

**Consequências.**

- (+) Simplicidade e segurança para a web.
- (+) Revogação de sessão/token fácil.
- (−) App mobile exigirá fluxo de token bem definido.
- (−) Dois mecanismos para testar.

---

## ADR-011 — Self-hosted e privacidade por padrão

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Dados financeiros são sensíveis; parte do público valoriza controle
e desconfia de SaaS. O solicitante definiu ambiente Docker.

**Decisão.** Produto operável em um host próprio via Docker Compose, sem
dependência obrigatória de terceiros. Telemetria opt-in e anonimizada. Exportação
e exclusão completas.

**Alternativas.** SaaS multiusuário; híbrido.

**Consequências.**

- (+) Diferencial de confiança e controle.
- (+) Menor custo recorrente para o operador.
- (−) O operador assume backups, TLS e atualizações.
- (−) Suporte e distribuição mais complexos.

---

## ADR-012 — Open Finance fora do MVP

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Open Finance reduz fricção, mas exige consentimento, parceria,
segurança de tokens e conformidade. O MVP entrega valor com entrada manual.

**Decisão.** MVP manual; importação CSV/OFX como P1; Open Finance como P2, atrás
de um adapter (`integrations`) sem acoplar o domínio.

**Alternativas.** Integrar desde o início; ignorar permanentemente.

**Consequências.**

- (+) Menor risco regulatório e técnico no lançamento.
- (+) Foco no núcleo (plano).
- (−) Mais digitação no início.
- (−) Integração futura exigirá investimento.

---

## ADR-013 — Estratégia híbrida como recomendação padrão

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** A literatura mostra trade-off entre eficiência (avalanche) e
motivação (snowball). O produto precisa de um padrão, mas sem impor.

**Decisão.** Recomendar híbrida quando houver quick wins; caso contrário,
avalanche. Sempre exibir comparação com snowball e o custo da escolha. O usuário
pode trocar e travar dívidas.

**Alternativas.** Sempre avalanche; sempre snowball; deixar sem recomendação.

**Consequências.**

- (+) Equilíbrio entre juros e motivação.
- (+) Transparência e autonomia.
- (−) Regra de quick win precisa de calibração com dados reais.
- (−) Mais complexidade de explicação na UI.

---

## ADR-014 — Mínimo existencial como piso, não soma

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Somar despesas essenciais e mínimo existencial duplicaria a reserva
e produziria planos artificialmente inviáveis. A Lei nº 14.181/2021 exige
preservar o mínimo existencial.

**Decisão.** `piso_essencial = max(despesas_essenciais, minimo_existencial)`.
O motor nunca sugere pagamento que reduza o disponível abaixo do piso. A memória
de cálculo é exibida.

**Alternativas.** Somar; usar apenas despesas essenciais; ignorar.

**Consequências.**

- (+) Realismo e conformidade ética/legal.
- (+) Evita dupla contagem.
- (−) Usuário pode informar valores inconsistentes; precisa de orientação.
- (−) Conceito exige educação no onboarding.

---

## ADR-015 — Plano inviável é um resultado de primeira classe

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Gerar um calendário quando os mínimos não cabem no orçamento seria
enganoso e perigoso. O usuário precisa de diagnóstico honesto.

**Decisão.** Retornar `status=infeasible` com motivo e caminhos alternativos
(corte, renda extra, renegociação), sem calendário. Nunca “esconder” o déficit.

**Alternativas.** Gerar plano mesmo assim; reduzir essenciais automaticamente.

**Consequências.**

- (+) Confiança e segurança.
- (+) Direciona para ações úteis.
- (−) Pode gerar frustração; mitigado por copy acolhedora e alternativas.
- (−) Exige UX específica para o estado inviável.

---

## ADR-016 — Localização BRL/pt-BR com modelo preparado para moeda

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** O público inicial é brasileiro; multimoeda não é prioridade, mas
não deve exigir reescrita.

**Decisão.** UI em pt-BR, BRL, `America/Sao_Paulo`. `profiles.currency` e
`accounts` preparados; conversão cambial fora do MVP.

**Alternativas.** Multimoeda desde o início; hardcode BRL.

**Consequências.**

- (+) Simplicidade e foco.
- (+) Evolução possível sem migração estrutural grande.
- (−) Usuários fora do Brasil não são atendidos no MVP.
- (−) Regras de formatação ainda centralizadas.

---

## ADR-017 — E-mail transacional via SMTP configurável

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Recuperação de senha e lembretes exigem e-mail; o operador
self-hosted pode ter provedor próprio.

**Decisão.** SMTP via variáveis de ambiente; templates transacionais; Mailpit em
desenvolvimento. Sem valores financeiros detalhados no corpo.

**Alternativas.** Provedor único (SES/SendGrid); sem e-mail.

**Consequências.**

- (+) Flexível e portável.
- (+) Fácil testar localmente.
- (−) Requer configuração e monitoramento de entrega.
- (−) Risco de spam sem SPF/DKIM/DMARC (documentar).

---

## ADR-018 — Um plano ativo por usuário

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** Múltiplos planos ativos confundem a execução e o dashboard. O
histórico ainda é necessário.

**Decisão.** Índice único parcial garante um `status='active'` por usuário.
Gerar novo plano arquiva o anterior. Planos antigos permanecem consultáveis.

**Alternativas.** Vários planos ativos; apenas um plano no total.

**Consequências.**

- (+) Clareza sobre “o plano atual”.
- (+) Histórico preservado.
- (−) Geração precisa ser transacional (arquivar + criar).
- (−) Concorrência exige lock/constraint.

---

## ADR-019 — Material Design 3 + Glassmorphism

**Status:** Aceito · **Data:** 2026-11-19

**Contexto.** A direção de frontend definida é "Material UX + Glassmorphism".
Era necessário conciliar uma linguagem de componentes consolidada e acessível
com uma identidade visual moderna, sem cair em excesso de transparência nem
comprometer performance/legibilidade.

**Decisão.** Adotar **Material Design 3** como sistema de UX (tipografia, cor
tonal, componentes, estados, movimento e layout) e **Glassmorphism** como
**camada de superfície** restrita a app bar, 1–2 cards de KPI, overlays, bottom
nav e snackbars. Implementar com `@material/web` + Tailwind + tokens CSS
próprios, com fallback sólido e `prefers-reduced-transparency`.

**Alternativas.** UI kit genérico; glass em toda a interface; SPA com MUI;
design system proprietário do zero.

**Consequências.**

- (+) Consistência e acessibilidade com componentes M3.
- (+) Identidade visual diferenciada sem sacrificar legibilidade.
- (+) Fallback e limites de uso preservam performance em devices modestos.
- (−) Duas linguagens visuais exigem disciplina de design.
- (−) `backdrop-filter` tem custo de GPU; exige teste e orçamento de camadas.
- (−) Necessidade de revisão de contraste em light/dark e sobre fundos.

**Referência:** [11-design-system-material-glass.md](11-design-system-material-glass.md).

---

## 20. Próximas decisões (pendentes)

| # | Decisão | Prazo | Responsável |
|---|---------|-------|-------------|
| P1 | Nome/identidade visual | Antes do beta | Produto |
| P2 | Modelo de monetização | Pós-MVP | Produto |
| P3 | MFA no MVP ou P1 | Fase 1 | Security |
| P4 | Importação OFX no MVP | Fase 2 | Produto |
| P5 | Workspace familiar P1/P2 | Fase 1 | Produto |
| P6 | Provedor de e-mail recomendado | Fase 4 | Ops |
| P7 | Política de retenção de auditoria | Antes do beta | Jurídico/Security |
| P8 | Cor semente e nível de vidro definitivos | Antes do beta | Design/Produto |
| P9 | Tema escuro no MVP ou P1 | Fase 2 | Produto |

---

## 21. Como registrar um novo ADR

1. Copie o formato acima com o próximo número.
2. Descreva o contexto sem solução embutida.
3. Liste alternativas reais e trade-offs.
4. Registre consequências positivas e negativas.
5. Atualize o status para **Aceito** após revisão.
6. Se substituir outro ADR, marque o antigo como **Substituído** e referencie.
