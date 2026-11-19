# 11 — Design System: Material UX + Glassmorphism

**Objetivo:** definir a linguagem visual e de interação do produto, conciliando
**Material Design 3 (Material You)** como sistema de UX/componentes com
**Glassmorphism** como tratamento de superfície.

**Status:** Aceito · **Data:** 2026-11-19 · **Relacionado:** [PRD](PRD.md) ·
[Arquitetura](04-arquitetura-tecnica.md) · [ADR-019](10-adr-decisoes-arquiteturais.md)

---

## 1. Interpretação da direção

> **Material UX** = Material Design 3: hierarquia, componentes, estados,
> movimento, tipografia, acessibilidade e layout responsivo.
>
> **Glassmorphism** = camada visual translúcida com desfoque, usada em
> superfícies específicas (app bar, cards de destaque, overlays), nunca como
> substituto da estrutura ou da legibilidade.

**Decisão:** manter a arquitetura server-rendered (Django + HTMX) e implementar
Material 3 com **Material Web Components** (`@material/web`) + **Tailwind CSS**
para layout/utilitários + uma camada CSS própria de **tokens de vidro**.

> Se a intenção for usar **MUI/React** (SPA), isso conflita com o ADR-003 e exige
> revisão da arquitetura. Esta documentação assume Material 3 + HTMX.

---

## 2. Princípios de design

1. **Clareza primeiro.** O próximo passo financeiro deve ser óbvio em 5 segundos.
2. **Vidro com propósito.** Transparência só onde há fundo decorativo e conteúdo curto.
3. **Contraste garantido.** Nenhum texto sobre vidro abaixo de 4,5:1.
4. **Movimento discreto.** Animações explicam mudanças, não decoram.
5. **Consistência Material.** Componentes, estados e espaçamento seguem M3.
6. **Mobile-first.** Polegar, toque de 48 px, uma ação principal por tela.
7. **Acessibilidade não é opcional.** Teclado, leitor de tela, redução de movimento
   e de transparência.
8. **Performance percebida.** Vidro é caro; usar com parcimônia e fallback.

---

## 3. Fundação visual

### 3.1 Paleta (Material 3 roles)

A paleta é gerada a partir de uma **cor semente** e exposta em tokens semânticos.
Não usar hex avulso em componentes.

| Token | Light | Dark | Uso |
|-------|-------|------|-----|
| `--md-sys-color-primary` | `#0F766E` | `#5EEAD4` | Ações principais, foco |
| `--md-sys-color-on-primary` | `#FFFFFF` | `#003731` | Texto sobre primary |
| `--md-sys-color-primary-container` | `#CCFBF1` | `#115E59` | Destaques suaves |
| `--md-sys-color-secondary` | `#2563EB` | `#93C5FD` | Links, ações secundárias |
| `--md-sys-color-tertiary` | `#B45309` | `#FCD34D` | Atenção positiva/negocial |
| `--md-sys-color-error` | `#DC2626` | `#FCA5A5` | Erro, risco crítico |
| `--md-sys-color-success` | `#16A34A` | `#86EFAC` | Quitação, progresso |
| `--md-sys-color-surface` | `#F8FAFC` | `#0B1220` | Fundo base |
| `--md-sys-color-surface-container` | `#FFFFFF` | `#111827` | Cards sólidos |
| `--md-sys-color-on-surface` | `#0F172A` | `#E2E8F0` | Texto principal |
| `--md-sys-color-on-surface-variant` | `#475569` | `#94A3B8` | Texto secundário |
| `--md-sys-color-outline` | `#CBD5E1` | `#334155` | Bordas |

**Regras**

- Contraste mínimo: 4,5:1 para texto normal; 3:1 para texto grande e ícones.
- Estados usam `primary`/`error` + ícone + texto (nunca só cor).
- Gráficos usam paleta categórica acessível e padrões (tracejado/rótulo).

### 3.2 Tipografia

| Papel | Fonte | Tamanho/linha | Peso |
|-------|-------|---------------|------|
| Display | Roboto Flex | 32/40 | 600 |
| Headline | Roboto Flex | 24/32 | 600 |
| Title | Roboto Flex | 20/28 | 600 |
| Body | Roboto Flex | 16/24 | 400 |
| Body small | Roboto Flex | 14/20 | 400 |
| Label | Roboto Flex | 14/20 | 500 |
| Caption | Roboto Flex | 12/16 | 500 |

- Variable font self-hosted, subset pt-BR + números.
- Números financeiros usam `font-variant-numeric: tabular-nums`.
- Escala em `rem`; suportar zoom de 200% sem quebra.
- Máximo ~75 caracteres por linha em textos longos.

### 3.3 Espaçamento, forma e elevação

| Token | Valor | Uso |
|-------|-------|-----|
| `--space-1` | 4 px | Ajustes finos |
| `--space-2` | 8 px | Ícone + texto |
| `--space-3` | 12 px | Componentes compactos |
| `--space-4` | 16 px | Padding padrão |
| `--space-6` | 24 px | Seções |
| `--space-8` | 32 px | Blocos |
| `--space-12` | 48 px | Páginas |

| Raio | Valor | Uso |
|------|-------|-----|
| `--radius-sm` | 8 px | Chips, inputs |
| `--radius-md` | 12 px | Cards |
| `--radius-lg` | 16 px | Painéis |
| `--radius-xl` | 24 px | Sheets/dialogs |
| `--radius-full` | 999 px | FAB, avatares |

**Elevação M3:** níveis 0–5. O vidro combina **sombra suave + borda clara +
desfoque**; não empilhar sombras fortes.

### 3.4 Breakpoints e layout

| Breakpoint | Largura | Navegação |
|------------|---------|-----------|
| Compact | < 600 px | Bottom navigation |
| Medium | 600–904 px | Navigation rail |
| Expanded | 905–1239 px | Rail + conteúdo |
| Large | ≥ 1240 px | Drawer + conteúdo |

- Conteúdo máximo: 1200 px; formulários, 640 px.
- Grid de 4/8/12 colunas; gutter 16/24 px.
- Safe areas mobile (`env(safe-area-inset-*)`).

### 3.5 Movimento

| Token | Duração | Uso |
|-------|---------|-----|
| `--motion-fast` | 150 ms | Hover, foco |
| `--motion-base` | 200 ms | Expansão, troca de estado |
| `--motion-emphasized` | 300 ms | Entrada de sheet/dialog |

- Easing: `cubic-bezier(0.2, 0, 0, 1)` (M3 emphasized).
- Respeitar `prefers-reduced-motion`: remover parallax, shimmer e transições longas.
- Nunca animar `backdrop-filter` ou propriedades de layout.

---

## 4. Glassmorphism: regras de uso

### 4.1 Tokens de vidro

```css
:root {
  --glass-blur: 16px;
  --glass-saturate: 140%;

  --glass-bg-light: rgba(255, 255, 255, 0.55);
  --glass-border-light: rgba(255, 255, 255, 0.45);
  --glass-bg-dark: rgba(15, 23, 42, 0.55);
  --glass-border-dark: rgba(148, 163, 184, 0.25);

  --glass-shadow: 0 8px 32px rgba(15, 23, 42, 0.12);
  --glass-scrim: rgba(248, 250, 252, 0.72);

  --glass-radius: var(--radius-lg);
}

.glass {
  background: var(--glass-bg-light);
  border: 1px solid var(--glass-border-light);
  border-radius: var(--glass-radius);
  box-shadow: var(--glass-shadow);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
}

@media (prefers-color-scheme: dark) {
  .glass {
    background: var(--glass-bg-dark);
    border-color: var(--glass-border-dark);
  }
}

/* Fallback: sem suporte ou transparência reduzida */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass { background: var(--md-sys-color-surface-container); }
}

@media (prefers-reduced-transparency: reduce) {
  .glass {
    background: var(--md-sys-color-surface-container);
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
}
```

### 4.2 Onde usar

| Superfície | Vidro? | Observação |
|------------|--------|------------|
| App bar / top bar | Sim | Sticky, com scrim ao rolar |
| Card de KPI ("saldo livre") | Sim | Apenas 1–2 por tela |
| Card de plano/resumo | Sim | Conteúdo curto |
| Bottom navigation | Sim | Com fallback sólido |
| Dialog/sheet | Parcial | Scrim de vidro; superfície do dialog sólida |
| Snackbar/toast | Sim | Alto contraste |
| Formulários | Não | Superfície sólida para legibilidade |
| Tabelas/listas densas | Não | Fundo sólido, zebra sutil |
| Texto longo | Não | Nunca sobre fundo ocupado |
| Gráficos | Não | Fundo sólido; vidro só no container |

### 4.3 Regras de ouro

1. **Máximo 2 camadas de vidro** sobrepostas.
2. **Máximo ~8 superfícies de vidro por viewport**; em listas longas, desligar.
3. **Sempre** borda 1 px clara + sombra suave para separar do fundo.
4. **Nunca** texto pequeno sobre vidro sem scrim/tinta que garanta contraste.
5. **Fundo** deve ser estático (gradiente/mesh), não vídeo/animado.
6. **Fallback** obrigatório para navegadores sem `backdrop-filter`.
7. **Teste** em Android intermediário; medir FPS antes de ampliar o uso.
8. **Não** usar vidro para indicar estado (erro/sucesso) — usar cor + ícone + texto.

### 4.4 Fundo decorativo

```css
.app-background {
  min-height: 100dvh;
  background:
    radial-gradient(60% 50% at 10% 0%, rgba(15, 118, 110, 0.18), transparent 60%),
    radial-gradient(50% 40% at 90% 10%, rgba(37, 99, 235, 0.16), transparent 60%),
    radial-gradient(40% 40% at 50% 100%, rgba(180, 83, 9, 0.10), transparent 60%),
    var(--md-sys-color-surface);
  background-attachment: fixed;
}
```

- Sem imagens pesadas no MVP; gradientes leves preservam performance.
- Em dark mode, reduzir opacidade dos gradientes.
- Não usar blur animado no fundo.

---

## 5. Componentes (Material 3)

### 5.1 Inventário

| Componente | Uso no produto | Variante |
|------------|----------------|----------|
| Top app bar | Título, voltar, ações | Small/medium, glass |
| Navigation bar | Mobile | 4–5 destinos |
| Navigation rail/drawer | Tablet/desktop | Expandable |
| Button | Ações | Filled, tonal, outlined, text |
| FAB | "Novo lançamento" | Primary, mobile |
| Card | KPIs, dívidas, resumo | Elevated/filled + glass |
| Text field | Formulários | Outlined |
| Select/Menu | Categorias, filtros | Outlined |
| Chip | Filtros, tags | Filter/assist |
| Segmented button | Estratégia (avalanche/snowball/híbrida) | Single-select |
| Slider | Simulador | Continuous + valor |
| Switch | Preferências | — |
| Dialog | Confirmações destrutivas | Solid surface + glass scrim |
| Bottom sheet | Ações rápidas, filtros | Mobile |
| Snackbar | Feedback | Glass, 4 s |
| Progress | Onboarding, plano | Linear/circular |
| Tabs | Detalhe de dívida | Primary/secondary |
| Data table | Transações/calendário | Custom, responsivo |
| Tooltip | Ajuda contextual | — |
| Empty state | Sem dados | Ilustração + CTA |

### 5.2 Especificações de componentes-chave

**Botão primário (filled)**

- Altura 40 px (48 px em mobile), raio full.
- `primary` + `on-primary`; estado hover 8%, pressed 12%, focus ring 2 px.
- Ícone opcional à esquerda; label 14/20 medium.
- Loading: spinner 16 px + label "Salvando…", `aria-busy`.

**Card de KPI (glass)**

- Padding 24 px; raio 16 px; borda 1 px; blur 16 px.
- Rótulo 12/16, valor 32/40 tabular, delta com ícone e cor semântica.
- Ação opcional "ver detalhes" (text button).
- Máximo 2 por viewport; em telas pequenas, empilhar.

**Text field (outlined)**

- Altura 56 px; label flutuante; helper text 12/16.
- Erro: borda `error`, ícone + mensagem; `aria-invalid` e `aria-describedby`.
- Moeda: prefixo `R$`, máscara, teclado numérico (`inputmode="decimal"`).
- Autocomplete em credores/categorias.

**Tabela de transações**

- Cabeçalho sticky, fundo sólido.
- Colunas: data, descrição, categoria, valor (direita, tabular).
- Mobile: cards com rótulo/valor; não esconder informação essencial.
- Filtros em sheet no mobile; linha clicável com foco visível.

**Timeline do plano**

- Lista vertical com marcadores (não iniciado/atual/quitado).
- Cada item: credor, ordem, valor, mês, juros.
- Estado atual destacado com `primary-container`, não só cor.
- Resumo fixo (glass) com "quitação em X meses" e "juros economizados".

**Simulador**

- Slider com valor editável; `aria-valuetext` com R$.
- Resultado em cards comparativos (antes/depois), sólidos.
- Botão "Aplicar cenário" com confirmação.

### 5.3 Estados obrigatórios

- **Default, hover, focus, pressed, disabled, loading, error, empty, success.**
- Foco visível em todos os interativos (2 px, offset 2 px).
- Alvo de toque mínimo 48×48 px.
- Mensagens de erro associadas ao campo e anunciadas (`role="alert"`).
- Skeletons para carregamento; sem spinner de página inteira.

---

## 6. Padrões de tela

### 6.1 Shell da aplicação

```
┌─────────────────────────────────────────────┐
│ Top app bar (glass, sticky)                 │
├──────────┬──────────────────────────────────┤
│ Rail /   │ Conteúdo (max 1200px)            │
│ Drawer   │  ├─ Cabeçalho da página          │
│          │  ├─ Hero/KPI (glass, 1–2)        │
│          │  ├─ Cards/listas (sólidos)       │
│          │  └─ Ações                       │
└──────────┴──────────────────────────────────┘
```

- Mobile: top bar + bottom navigation + FAB.
- Desktop: rail/drawer + conteúdo.
- Título da página sempre visível; breadcrumb quando necessário.

### 6.2 Onboarding

- Stepper M3 (1 de 4), uma pergunta por tela.
- Painel glass sobre fundo decorativo; inputs sólidos.
- "Pular e completar depois" sempre disponível.
- Progresso salvo automaticamente.
- Copy acolhedora; sem vermelho agressivo.

### 6.3 Dashboard

- **Hero glass:** saldo livre + frase de ação ("Você pode pagar R$ X este mês").
- KPIs sólidos: dívida total, comprometimento, DTI.
- Próximo pagamento com CTA "Registrar pagamento".
- Alertas com ícone + texto + ação.
- Gráfico de evolução em card sólido.
- No máximo 2 superfícies de vidro.

### 6.4 Dívidas e plano

- Lista de dívidas em cards sólidos com barra de progresso.
- Detalhe: tabs (Resumo, Pagamentos, Simulação).
- Plano: resumo glass + timeline sólida + tabela do calendário.
- Explicação "por que esta dívida primeiro" em painel expansível.
- Comparação de estratégias em segmented button + cards.

### 6.5 Transações

- Lista densa sólida; agrupamento por data.
- FAB "Novo lançamento" (mobile) / botão no header (desktop).
- Formulário em sheet/dialog; foco no valor ao abrir.
- Filtros em sheet; chips de filtro ativos.
- Importação (P1) com preview e relatório.

### 6.6 Configurações e privacidade

- Listas M3 com ícones e descrições.
- Seções: Perfil financeiro, Aparência, Notificações, Segurança, Meus dados.
- Ações destrutivas com confirmação digitada.
- Exportação/exclusão com feedback claro.

---

## 7. Acessibilidade

| Requisito | Critério |
|-----------|----------|
| Contraste | 4,5:1 texto; 3:1 ícones/UI; validar sobre vidro |
| Teclado | Todos os fluxos operáveis; ordem lógica; Esc fecha overlays |
| Foco | Visível (2 px) e não obscurecido por sticky/glass |
| Leitor de tela | Labels, `aria-describedby`, erros anunciados, tabelas com headers |
| Toque | ≥ 48×48 px; espaçamento ≥ 8 px |
| Movimento | `prefers-reduced-motion` desliga animações não essenciais |
| Transparência | `prefers-reduced-transparency` troca vidro por sólido |
| Zoom | 200% sem perda de conteúdo; sem scroll horizontal |
| Cor | Nunca única portadora de significado; usar texto/ícone |
| Formulários | Autocomplete, `inputmode`, mensagens específicas |
| Vídeo/áudio | Sem autoplay; legendas se houver |

**Testes:** axe-core, Lighthouse, teste manual com NVDA/VoiceOver, navegação
somente teclado, contraste em light/dark.

---

## 8. Performance

O `backdrop-filter` é caro (GPU). Regras:

1. Orçar no máximo **8** superfícies de vidro por tela.
2. Não aplicar vidro em itens de listas longas (transações, calendário).
3. Evitar vidro em elementos que mudam de tamanho/posição durante scroll.
4. Não animar `backdrop-filter`, `filter`, `box-shadow` ou `background`.
5. Preferir gradientes estáticos a imagens/vídeo de fundo.
6. Em scroll, top bar pode trocar para sólida (economia + legibilidade).
7. Testar em dispositivo Android intermediário (CPU 4x mais lenta).
8. Medir: FPS, long tasks, Lighthouse mobile ≥ 90 (meta).
9. CSS crítico inline; JS de componentes com `defer`.
10. Ícones/fontes com subset e `font-display: swap`.

**Fallback progressivo:** sólido é o padrão; vidro é enhancement.

---

## 9. Implementação

### 9.1 Stack de frontend

| Camada | Escolha |
|--------|---------|
| Componentes | `@material/web` (Material Web Components) |
| Layout/utilitários | Tailwind CSS |
| Interatividade | HTMX + Alpine.js (pontual) |
| Ícones | Material Symbols Rounded (self-hosted) |
| Tipografia | Roboto Flex (self-hosted, subset) |
| Build | Vite ou esbuild → `static/vendor/` |
| Templates | Django Templates |

**Sem CDN em produção** (privacidade, disponibilidade e CSP). Assets versionados
e servidos pelo Nginx.

### 9.2 Estrutura de arquivos

```
src/static/
├── css/
│   ├── tokens.css          # cores, tipografia, spacing, glass
│   ├── material.css        # overrides M3
│   └── app.css             # componentes e utilitários
├── js/
│   ├── app.js              # HTMX/Alpine init
│   └── vendor/             # material-web bundle
├── fonts/
│   ├── roboto-flex.woff2
│   └── material-symbols.woff2
└── img/
```

### 9.3 Tailwind + tokens

```js
// tailwind.config.js (ilustrativo)
export default {
  content: ["./src/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        primary: "var(--md-sys-color-primary)",
        "on-primary": "var(--md-sys-color-on-primary)",
        surface: "var(--md-sys-color-surface)",
        "on-surface": "var(--md-sys-color-on-surface)",
        error: "var(--md-sys-color-error)",
        success: "var(--md-sys-color-success)",
      },
      borderRadius: {
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: { glass: "var(--glass-shadow)" },
    },
  },
};
```

> Usar tokens semânticos; evitar `bg-[#...]` e valores mágicos.

### 9.4 Exemplo de card glass (Django + Tailwind)

```html
<article class="glass p-6 rounded-xl max-w-md" aria-labelledby="free-cash-title">
  <p id="free-cash-title" class="text-label text-on-surface-variant">
    Você pode pagar este mês
  </p>
  <p class="text-display font-semibold tabular-nums text-on-surface">
    R$ {{ free_cash|floatformat:2 }}
  </p>
  <p class="text-body-sm text-on-surface-variant">
    Depois do essencial e das parcelas mínimas.
  </p>
  <md-filled-button href="{% url 'plans:current' %}" class="mt-4">
    Ver meu plano
  </md-filled-button>
</article>
```

> `@material/web` usa **custom elements** (`<md-filled-button>`, `<md-outlined-text-field>`),
> não classes CSS. O Tailwind cuida de layout/espaçamento; o Material cuida do
> componente e dos estados.

### 9.5 HTMX com Material

- `hx-boost="true"` no shell para navegação parcial.
- `hx-target` em regiões (ex.: `#plan-summary`), `hx-swap="innerHTML"`.
- `hx-indicator` aponta para skeleton/spinner.
- CSRF: `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`.
- Erros de validação retornam o partial com mensagens e status 422.
- Material Web dispara eventos padrão (`input`, `change`); integrar com Alpine
  quando necessário.
- **Progressive enhancement:** formulários e navegação essenciais funcionam com
  HTML/servidor; JS de componentes é melhoria, não pré-requisito.
- Não usar HTMX para cálculos financeiros; o servidor é a fonte da verdade.

### 9.6 Tema (light/dark)

- `prefers-color-scheme` como padrão; preferência explícita do usuário sobrepõe.
- Tokens escopados em `:root[data-theme="dark"]` e `:root[data-theme="light"]`
  para permitir alternância manual sem depender só da media query.
- Alternância grava em `profile.theme` (P1) ou `localStorage` + cookie.
- Vidro tem tokens distintos por tema; nunca usar branco puro no dark.
- Testar contraste nos dois temas.

---

## 10. Conteúdo e tom

- **Voz:** direta, acolhedora, sem julgamento.
- **Números:** "R$ 1.234,56"; percentuais com 2 casas quando relevante.
- **Datas:** "12 de dezembro de 2026" ou "12/12/2026" (consistente).
- **Erros:** o que aconteceu + como resolver; sem culpar o usuário.
- **Estados vazios:** explicar o valor e oferecer a primeira ação.
- **Disclaimers:** visíveis, mas não alarmistas.
- **Nunca** prometer resultado financeiro.

Exemplos:

| Contexto | Evitar | Preferir |
|----------|--------|----------|
| Orçamento negativo | "Você estourou o orçamento." | "Seu orçamento não fecha este mês. Vamos ajustar?" |
| Dívida cara | "Você está perdendo dinheiro." | "Esta dívida cresce mesmo pagando o mínimo." |
| Plano inviável | "Impossível." | "Com essa renda, os mínimos não cabem. Veja caminhos." |
| Sucesso | "Parabéns, você é ótimo!" | "Você quitou mais uma dívida. Faltam 2." |

---

## 11. Anti-padrões

1. Vidro em tudo: perda de hierarquia, contraste e performance.
2. Texto sobre gradiente sem scrim.
3. Múltiplos blurs aninhados e animados.
4. Misturar Material 2 e 3 (ícones, sombras, formas).
5. Sombras fortes + bordas + vidro ao mesmo tempo.
6. Cards de KPI gigantes que empurram a ação para fora da tela.
7. Tabela densa sobre fundo translúcido.
8. Foco invisível ou escondido atrás de sticky.
9. Animações de scroll/parallax no fluxo financeiro.
10. Ícones sem rótulo em ações destrutivas.
11. Cores semânticas usadas como decoração.
12. Copy que culpa ou envergonha o usuário.

---

## 12. Checklist de QA visual e acessibilidade

### Visual
- [ ] Tokens aplicados; nenhum hex avulso.
- [ ] Light/dark testados.
- [ ] Vidro apenas nas superfícies permitidas (≤ 8 por tela).
- [ ] Fallback sólido sem `backdrop-filter`.
- [ ] `prefers-reduced-transparency` e `prefers-reduced-motion` testados.
- [ ] Layout em 360, 600, 905, 1240 e 1440 px.
- [ ] FAB/bottom nav não cobrem conteúdo (safe area).
- [ ] Estados vazio, loading, erro e sucesso desenhados.

### Acessibilidade
- [ ] Contraste ≥ 4,5:1 (texto) e 3:1 (UI/ícones), inclusive sobre vidro.
- [ ] Navegação completa por teclado, com foco visível.
- [ ] Labels e mensagens de erro associados.
- [ ] Tabelas com `<th scope>`, legendas e resumo.
- [ ] Toque ≥ 48×48 px.
- [ ] Zoom 200% sem scroll horizontal.
- [ ] Leitor de tela: fluxos de onboarding, plano e pagamento.
- [ ] `aria-live` para feedback assíncrono (HTMX).

### Performance
- [ ] Lighthouse mobile ≥ 90 (performance/acessibilidade).
- [ ] Sem jank ao rolar com vidro.
- [ ] Fontes/ícones com subset e `font-display: swap`.
- [ ] JS de componentes com `defer`; CSS crítico.
- [ ] Teste em Android intermediário.

---

## 13. Governança

- Tokens vivem em `src/static/css/tokens.css` e no `tailwind.config.js`.
- Componentes novos exigem: estados, acessibilidade, uso de token e exemplo.
- Mudanças visuais relevantes passam por revisão de design e QA.
- Snapshot visual (P1) para detectar regressões.
- Este documento é a fonte da verdade visual; ADRs registram mudanças estruturais.

---

## 14. Decisões e pendências

| # | Decisão | Status |
|---|---------|--------|
| D1 | Material Design 3 como base de UX | Aceito |
| D2 | Glassmorphism como superfície de destaque | Aceito |
| D3 | Material Web + Tailwind + HTMX (sem SPA) | Aceito |
| D4 | Self-host de fontes, ícones e componentes | Aceito |
| D5 | Semente de cor definitiva (teal vs. azul) | Pendente (marca) |
| D6 | Nível de vidro (sutil vs. expressivo) | Pendente (teste com usuários) |
| D7 | Biblioteca de gráficos (Chart.js vs. ECharts) | Pendente (P1) |
| D8 | Tema escuro no MVP ou P1 | Pendente |

> D5–D8 não bloqueiam a Fase 1; usar os valores propostos e validar no protótipo.
