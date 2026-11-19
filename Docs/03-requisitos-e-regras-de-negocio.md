# 03 — Requisitos e Regras de Negócio

**Objetivo:** especificar o comportamento funcional e não funcional do sistema,
com regras de negócio rastreáveis e critérios de aceite verificáveis.

---

## 1. Convenções

- **P0:** obrigatório no MVP, bloqueia lançamento.
- **P1:** importante, primeira evolução.
- **P2:** futuro, não bloqueia.
- **RN:** regra de negócio (numerada).
- **RF:** requisito funcional.
- **RNF:** requisito não funcional.
- Valores monetários em `Decimal` (2 casas), arredondamento **half-up**.
- Taxas em fração decimal mensal; conversão documentada em [06](06-motor-plano-regularizacao.md).
- Toda escrita relevante gera `audit_log`.
- Toda entidade de negócio tem `id` UUID, `created_at`, `updated_at`, `deleted_at` (soft delete quando aplicável).

---

## 2. Papéis e permissões

| Papel | Escopo | Permissões |
|-------|--------|------------|
| **Anônimo** | — | Cadastro, login, recuperação de senha, páginas públicas |
| **Usuário** | Próprios dados | CRUD nos próprios recursos; exportar; excluir conta |
| **Owner de workspace** (P1) | Workspace familiar | Convidar/remover membros, definir papéis, ver consolidado |
| **Membro** (P1) | Workspace | Ver/editar dados compartilhados conforme papel; manter privados |
| **Operador/Admin** | Instância | Acesso a métricas operacionais e suporte; **sem** acesso a dados financeiros por padrão |

**RN-P01 — Isolamento:** toda query de negócio filtra por `user_id` (ou
`workspace_id` no P1). Testes automatizados devem tentar acesso cruzado e falhar.

**RN-P02 — Admin:** acesso a dados de usuário só com consentimento explícito e
registro de auditoria (impersonação desabilitada por padrão).

---

## 3. Requisitos funcionais

### 3.1 Conta e autenticação

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-A01 | Cadastro com e-mail e senha | P0 | E-mail único, verificação assíncrona |
| RF-A02 | Login/logout com sessão segura | P0 | Cookies HttpOnly/Secure/SameSite |
| RF-A03 | Recuperação de senha por e-mail | P0 | Token de uso único, expiração 30 min |
| RF-A04 | Alteração de senha | P0 | Exige senha atual; invalida outras sessões |
| RF-A05 | MFA TOTP | P1 | Opt-in; códigos de recuperação |
| RF-A06 | Exclusão de conta | P0 | Confirmação dupla; anonimização/exclusão |
| RF-A07 | Aceite de termos e privacidade | P0 | Versionado e auditado |

### 3.2 Perfil financeiro

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-B01 | Renda líquida mensal | P0 | `Decimal ≥ 0` |
| RF-B02 | Despesas essenciais mensais | P0 | Pode derivar de categorias marcadas como essenciais |
| RF-B03 | Mínimo existencial | P0 | Sugerido, editável, `≥ 0` |
| RF-B04 | Moeda e fuso | P0 | BRL / America/Sao_Paulo; modelo preparado |
| RF-B05 | Dependentes | P1 | Impacta sugestão de essenciais |
| RF-B06 | Perfil de renda variável | P1 | Média de 3 meses + fator conservador |
| RF-B07 | Reserva de emergência desejada | P1 | Meta separada |

### 3.3 Categorias e contas

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-C01 | CRUD de categorias | P0 | Tipo receita/despesa; ícone/cor opcional |
| RF-C02 | Marcar categoria como essencial | P0 | Base para orçamento |
| RF-C03 | Categorias padrão no onboarding | P0 | Seed por usuário |
| RF-C04 | CRUD de contas/carteiras | P0 | Conta corrente, poupança, dinheiro, cartão |
| RF-C05 | Arquivar categoria/conta | P1 | Não apaga histórico |
| RF-C06 | Subcategorias | P1 | Um nível |

### 3.4 Transações

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-D01 | CRUD de receitas e despesas | P0 | Valor, data, tipo, categoria, conta |
| RF-D02 | Status: pendente/pago | P0 | Despesa futura não entra no saldo realizado |
| RF-D03 | Transação parcelada | P0 | Gera N parcelas vinculadas |
| RF-D04 | Transação recorrente | P0 | Geração mensal idempotente |
| RF-D05 | Tags e observações | P1 | Busca por tag |
| RF-D06 | Anexos (comprovantes) | P2 | Storage local/S3 |
| RF-D07 | Importação CSV/OFX | P1 | Deduplicação e pré-visualização |
| RF-D08 | Transferência entre contas | P1 | Não conta como receita/despesa |
| RF-D09 | Estorno/cancelamento | P0 | Mantém histórico; não exclui fisicamente |
| RF-D10 | Busca e filtros | P0 | Período, tipo, categoria, conta, texto |

**RN-D01 — Saldo realizado:** soma de receitas pagas − despesas pagas no período.
Pendentes aparecem separadas como "previsto".

**RN-D02 — Recorrência:** a geração usa uma chave idempotente
`(recorrencia_id, competencia)`; se já existe, não cria duplicata.

**RN-D03 — Parcelamento:** a soma das parcelas deve ser igual ao valor total
(ajuste de centavos na última parcela).

**RN-D04 — Exclusão:** transações não são apagadas fisicamente no MVP; usam
`deleted_at` e ficam fora dos cálculos.

### 3.5 Dívidas

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-E01 | CRUD de dívidas | P0 | Credor, tipo, saldo, taxa, parcela, vencimento |
| RF-E02 | Taxa mensal ou anual | P0 | Pelo menos uma; converter |
| RF-E03 | CET opcional | P1 | Usado para exibição e comparação |
| RF-E04 | Parcela mínima | P0 | Obrigatória para simulação |
| RF-E05 | Status da dívida | P0 | ativa, quitada, renegociada, em_atraso |
| RF-E06 | Histórico de pagamentos | P0 | Valor, data, tipo, observação |
| RF-E07 | Ordem manual (travar dívida) | P1 | Respeitada pelo motor com aviso |
| RF-E08 | Renegociação | P1 | Nova taxa/prazo/saldo, preservando histórico |
| RF-E09 | Anexos de contrato | P2 | Documentos |
| RF-E10 | Alerta de amortização negativa | P0 | Parcela ≤ juros do mês |

**RN-E01 — Saldo devedor:** `saldo_atual` é o principal + juros acumulados
informado pelo usuário; o motor projeta a partir dele.

**RN-E02 — Taxa efetiva:** se o usuário informar taxa anual, converter para
mensal por juros compostos: `i_m = (1 + i_a)^(1/12) − 1`.
Se informar CET anual, usar como taxa efetiva anual e converter.

**RN-E03 — Parcela mínima:** deve ser `> 0`. Se `parcela_mínima ≤ saldo × i_m`,
marcar risco de amortização negativa.

**RN-E04 — Dívida quitada:** saldo deve ser 0 e status `quitada`; sai do plano
e o valor liberado é redistribuído.

**RN-E05 — Dívida em atraso:** status `em_atraso` exige revisão; motor usa o
saldo atual e alerta sobre encargos.

### 3.6 Diagnóstico e dashboard

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-F01 | Saldo do mês | P0 | Receitas − despesas pagas |
| RF-F02 | Dívida total | P0 | Soma dos saldos ativos |
| RF-F03 | Taxa de comprometimento | P0 | Parcelas mínimas ÷ renda líquida |
| RF-F04 | DTI | P0 | Parcelas ÷ renda bruta (se informada) |
| RF-F05 | Saldo livre | P0 | Fórmula da RN-F01 |
| RF-F06 | Próximo pagamento recomendado | P0 | Do plano ativo |
| RF-F07 | Evolução mensal | P1 | Gráfico dos últimos 6 meses |
| RF-F08 | Alertas | P0 | Ver RN-F03 |
| RF-F09 | "Como calculamos" | P0 | Memória de cálculo por indicador |

**RN-F01 — Saldo livre:**

```
piso_essencial = max(despesas_essenciais_do_mes, minimo_existencial)

renda_liquida
− piso_essencial
− parcelas_minimas_das_dividas
− outras_despesas_planejadas_do_mes
= saldo_livre
```

O mínimo existencial **não é somado** se já estiver contido nas despesas
essenciais. O sistema usa `max(despesas_essenciais, minimo_existencial)` como
piso, nunca a soma dupla.

**RN-F02 — Comprometimento:**

```
comprometimento = soma(parcelas_minimas) / renda_liquida
```

**RN-F03 — Faixas de alerta:**

| Condição | Severidade | Mensagem |
|----------|------------|----------|
| saldo_livre < 0 | Crítico | "Seu orçamento não fecha. Vamos ajustar?" |
| comprometimento > 50% | Crítico | "Mais da metade da renda está comprometida." |
| comprometimento > 30% | Alerta | "Evite novas dívidas; priorize quitação." |
| parcela ≤ juros | Crítico | "Esta dívida cresce mesmo pagando o mínimo." |
| sem reserva e dívida cara | Alerta | "Considere reserva mínima de 1 mês." |
| plano > 60 meses | Alerta | "Prazo longo; considere renegociar." |

**RN-F04 — Dados insuficientes:** sem renda > 0 e ao menos 1 dívida ativa, o
diagnóstico mostra estado vazio com CTA, não números zerados enganosos.

### 3.7 Motor de plano

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-G01 | Estratégias avalanche/snowball/híbrida | P0 | Ver [06](06-motor-plano-regularizacao.md) |
| RF-G02 | Ordem explicável | P0 | Justificativa por dívida |
| RF-G03 | Calendário mês a mês | P0 | Até 600 meses (limite de segurança) |
| RF-G04 | Data estimada de quitação | P0 | Por dívida e total |
| RF-G05 | Total de juros e total pago | P0 | Por dívida e total |
| RF-G06 | Comparação de estratégias | P0 | Lado a lado |
| RF-G07 | Plano versionado | P0 | Snapshot de parâmetros e resultados |
| RF-G08 | Recalcular após mudanças | P0 | Renda, despesa, dívida, pagamento |
| RF-G09 | Detecção de inviabilidade | P0 | Mínimos > orçamento disponível |
| RF-G10 | Aporte extra e cenários | P0 | Simulador |
| RF-G11 | Plano de contingência | P1 | Só mínimos + essenciais |

**RN-G01 — Orçamento para dívidas:**

```
piso_essencial = max(despesas_essenciais, minimo_existencial)
orcamento_dividas = renda_liquida − piso_essencial − outras_despesas_planejadas
```

Deve ser `> 0`. Se `soma(parcelas_minimas) > orcamento_dividas`, o plano é
**inviável**: exibir déficit e caminhos (corte, renda extra, renegociação),
sem gerar calendário enganoso.

**RN-G02 — Ordem avalanche:** maior `taxa_efetiva_mensal`; desempate por menor
saldo e depois por vencimento.

**RN-G03 — Ordem snowball:** menor `saldo_atual`; desempate por maior taxa e
depois por vencimento.

**RN-G04 — Híbrida:** quick wins (saldo ≤ 2 × excedente mensal **ou** ≤ 10% da
dívida total) ordenados por saldo; depois avalanche. Limite configurável.

**RN-G05 — Rollover:** ao quitar uma dívida, sua parcela liberada é adicionada ao
excedente do mês seguinte (efeito bola de neve).

**RN-G06 — Juros:** capitalização mensal; juros do mês = saldo × taxa mensal,
arredondado a 2 casas. Pagamentos abatem juros e depois principal (ordem padrão
de amortização). O usuário pode informar o valor exato pago.

**RN-G07 — Limite de simulação:** 600 meses. Se não quitar, retornar
`prazo_excedido` com aviso, não loop infinito.

**RN-G08 — Determinismo:** mesmos inputs + mesma estratégia + mesma versão do
motor ⇒ mesmos outputs. Registrar `engine_version`.

### 3.8 Simulador

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-H01 | Simular corte de despesa | P0 | Impacto em prazo/juros |
| RF-H02 | Simular renda extra | P0 | Única ou recorrente |
| RF-H03 | Simular renegociação | P1 | Taxa, prazo, desconto |
| RF-H04 | Comparar cenários | P0 | Até 3 cenários |
| RF-H05 | Aplicar cenário ao plano | P1 | Com confirmação |
| RF-H06 | Aviso de premissas | P0 | Juros constantes, sem imprevistos |

**RN-H01 — Simulação não altera dados reais** até o usuário aplicar explicitamente.

**RN-H02 — Cenário conservador:** renda × fator (padrão 80%) e despesas × fator
(padrão 110%), configurável.

### 3.9 Pagamentos e acompanhamento

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-I01 | Registrar pagamento | P0 | Mínimo, parcela ou extra |
| RF-I02 | Idempotência | P0 | `Idempotency-Key` / chave única |
| RF-I03 | Recalcular plano | P0 | Após pagamento ou edição |
| RF-I04 | Marcar parcela como paga | P0 | A partir do calendário |
| RF-I05 | Histórico | P0 | Ordenado, filtrável |
| RF-I06 | Lembretes | P1 | E-mail/push no vencimento |
| RF-I07 | Aderência | P1 | % de parcelas pagas no prazo |

**RN-I01 — Pagamento parcial:** se `valor < juros`, o saldo aumenta; alertar.
Se `juros < valor < parcela`, abate o que for possível e mantém status.

**RN-I02 — Registro retroativo:** permitido; recalcula a partir da competência
do pagamento.

### 3.10 Relatórios, exportação e privacidade

| ID | Requisito | Prio | Notas |
|----|-----------|------|-------|
| RF-J01 | Resumo mensal | P0 | Receitas, despesas, dívidas |
| RF-J02 | Exportar CSV/JSON | P0 | Todos os dados do usuário |
| RF-J03 | Exportar PDF | P1 | Relatório do plano |
| RF-J04 | Excluir conta/dados | P0 | LGPD |
| RF-J05 | Consentimentos | P0 | Versionados |
| RF-J06 | Log de auditoria do titular | P1 | Acessos e alterações |

---

## 4. Requisitos não funcionais

| ID | Categoria | Requisito | Critério |
|----|-----------|-----------|----------|
| RNF-01 | Performance | Páginas principais | P95 < 800 ms em 100 usuários simultâneos |
| RNF-02 | Performance | Motor de plano | < 300 ms para 20 dívidas × 60 meses |
| RNF-03 | Performance | Consultas | Sem N+1; índice em FKs e campos de filtro |
| RNF-04 | Escalabilidade | MVP | 1.000 usuários, 100k transações, 1 host |
| RNF-05 | Disponibilidade | Mensal | 99,5% (self-hosted) |
| RNF-06 | Segurança | Senhas | Argon2id, política mínima |
| RNF-07 | Segurança | Transporte | TLS 1.2+ obrigatório em produção |
| RNF-08 | Segurança | Sessão | Expiração, rotação, CSRF, SameSite |
| RNF-09 | Segurança | Rate limit | Login, recuperação, API |
| RNF-10 | Segurança | Dependências | Scan em CI; sem CVE crítica conhecida |
| RNF-11 | Privacidade | LGPD | Minimização, consentimento, portabilidade, exclusão |
| RNF-12 | Auditoria | Eventos | Login, alterações financeiras, exportação, exclusão |
| RNF-13 | Backup | RPO/RTO | RPO 24h / RTO 4h; restore testado |
| RNF-14 | Acessibilidade | WCAG | 2.2 AA |
| RNF-15 | Responsividade | Viewport | 360 px–1920 px |
| RNF-16 | Compatibilidade | Navegadores | 2 últimas versões Chrome/Firefox/Safari/Edge |
| RNF-17 | Observabilidade | Logs | JSON estruturado, request_id, sem PII |
| RNF-18 | Observabilidade | Health | `/healthz` (liveness) e `/readyz` (readiness) |
| RNF-19 | Portabilidade | Deploy | `docker compose up` documentado |
| RNF-20 | Manutenibilidade | Cobertura | ≥ 80% no domínio financeiro |
| RNF-21 | Localização | pt-BR | Textos, datas, moeda |
| RNF-22 | Ética | Disclaimer | Visível no plano e nos relatórios |
| RNF-23 | Design | Material 3 + Glassmorphism | Tokens, contraste AA, fallback sólido, ≤ 8 superfícies de vidro/tela |
| RNF-24 | Design | Performance visual | Lighthouse mobile ≥ 90; sem jank com `backdrop-filter` |
| RNF-25 | Design | Preferências | Respeitar `prefers-reduced-motion` e `prefers-reduced-transparency` |

---

## 5. Regras de negócio consolidadas

| ID | Regra | Onde |
|----|-------|------|
| RN-01 | Isolamento por usuário em toda query | RNF/Segurança |
| RN-02 | Valores em Decimal, half-up, 2 casas | Global |
| RN-03 | Juros mensais compostos; converter anual | Motor |
| RN-04 | Mínimo existencial é piso, não soma dupla | Diagnóstico |
| RN-05 | Plano inviável não gera calendário | Motor |
| RN-06 | Rollover de parcelas quitadas | Motor |
| RN-07 | Idempotência em recorrências e pagamentos | Transações/Dívidas |
| RN-08 | Soft delete e auditoria | Global |
| RN-09 | Ordem manual prevalece com aviso | Motor |
| RN-10 | Simulação não persiste sem confirmação | Simulador |
| RN-11 | Plano persiste snapshot e versão do motor | Motor |
| RN-12 | Exclusão de conta anonimiza logs | LGPD |
| RN-13 | Nenhum dado sensível em logs/telemetria | Observabilidade |
| RN-14 | Cálculos determinísticos e testáveis | Motor |
| RN-15 | Aviso legal em toda saída de plano | Produto |

---

## 6. Validações e mensagens

| Campo | Regra | Mensagem |
|-------|-------|----------|
| Valor | > 0, ≤ 9.999.999,99 | "Informe um valor maior que zero." |
| Data | Não futura para pagamentos | "A data do pagamento não pode ser futura." |
| Renda | > 0 para gerar plano | "Informe sua renda para calcular o plano." |
| Taxa | ≥ 0 e ≤ 100% a.m. | "Taxa inválida. Use o valor mensal, ex.: 1,99%." |
| Parcela | > 0 | "Informe a parcela mínima." |
| Saldo | ≥ 0 | "O saldo não pode ser negativo." |
| E-mail | Formato e único | "Este e-mail já está em uso." |
| Senha | ≥ 10 caracteres | "Use pelo menos 10 caracteres." |
| Parcelas | 2–360 | "Número de parcelas inválido." |
| Vencimento | Dia 1–31 | "Dia de vencimento inválido." |

---

## 7. Casos de borda obrigatórios

1. **Dívida com taxa 0** (familiar): funciona; ordem por saldo/vencimento.
2. **Parcela mínima ≤ juros:** detectar amortização negativa e alertar.
3. **Orçamento zero/negativo:** plano inviável; não gerar calendário.
4. **Dívida já quitada:** não entra no plano; valor não é redistribuído.
5. **Pagamento maior que o saldo:** limitar ao saldo, registrar troco/ajuste.
6. **Mês com 28/29/30/31 dias:** vencimento no último dia do mês se não existir.
7. **Virada de ano:** competência e parcelas futuras corretas.
8. **Mudança de renda no meio do plano:** recalcular a partir do mês corrente.
9. **Duas dívidas com mesma taxa/saldo:** desempate estável e documentado.
10. **Arredondamento:** última parcela absorve centavos; total fecha.
11. **Fuso horário:** datas de competência em `America/Sao_Paulo`.
12. **Usuário sem categorias:** seed automático no onboarding.
13. **Exclusão de categoria em uso:** bloquear ou reatribuir para "Outros".
14. **Recorrência editada:** futuro muda, passado preservado.
15. **Plano > 600 meses:** retornar aviso, não travar.
16. **Aporte extra maior que a dívida:** quita e redireciona o restante.
17. **Duas requisições simultâneas de pagamento:** idempotência garante uma só.
18. **Usuário tenta acessar dívida de outro:** 404 (não 403, para não vazar existência).

---

## 8. Critérios de aceite por área (resumo)

### Autenticação
- [ ] Login inválido não revela se o e-mail existe.
- [ ] Sessão expira por inatividade e logout invalida.
- [ ] Recuperação de senha não permite reutilização de token.

### Transações
- [ ] Soma de parcelas = total.
- [ ] Recorrência não duplica ao rodar duas vezes.
- [ ] Filtros retornam apenas dados do usuário.

### Dívidas
- [ ] Conversão anual ↔ mensal confere com casos conhecidos.
- [ ] Pagamento atualiza saldo e histórico.
- [ ] Quitação remove do plano e redistribui parcela.

### Plano
- [ ] Ordem avalanche/snowball/híbrida confere com exemplos da doc 06.
- [ ] Juros totais e prazo batem com cálculo manual em cenário controlado.
- [ ] Plano inviável retorna erro de negócio claro.
- [ ] Snapshot reproduz o mesmo resultado após mudança de dados.

### Segurança
- [ ] Acesso cruzado entre usuários retorna 404.
- [ ] CSRF ativo em formulários.
- [ ] Rate limit em login e recuperação.
- [ ] Nenhum dado financeiro em logs.

---

## 9. Matriz de rastreabilidade (amostra)

| Objetivo | Requisitos | Histórias | Métrica |
|----------|------------|-----------|---------|
| Diagnóstico claro | RF-F01..F09 | US-01, US-401 | Ativação |
| Plano acionável | RF-G01..G11 | US-02, US-501..504 | Planos gerados |
| Decisão consciente | RF-H01..H06 | US-03, US-601..603 | Uso do simulador |
| Execução | RF-I01..I07 | US-05, US-303, US-304 | Aderência |
| Privacidade | RF-J01..J06 | US-06, US-702, US-703 | Exportações/exclusões |
| Segurança | RNF-06..13 | Transversais | Incidentes = 0 |

---

## 10. Fora de escopo (requisitos)

- Recomendação personalizada de produtos financeiros.
- Cálculo de imposto de renda.
- Emissão de boletos, PIX ou pagamentos.
- Gestão de investimentos e criptoativos.
- Contabilidade empresarial.
- Score de crédito próprio.
