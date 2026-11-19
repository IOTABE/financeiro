# 04 — Arquitetura Técnica

**Objetivo:** definir a arquitetura do MVP, o ambiente Docker, a organização do
código, os fluxos de dados e os requisitos operacionais.

**Stack definida:** Docker + Django + PostgreSQL.
**Complementos propostos:** Redis, Celery, Nginx, Gunicorn, HTMX + Tailwind +
Material 3.
**UI:** Material Design 3 (`@material/web`) + Glassmorphism (tokens próprios).
Detalhes em [11-design-system-material-glass.md](11-design-system-material-glass.md).

---

## 1. Princípios arquiteturais

1. **Monólito modular** — simplicidade operacional, com fronteiras claras por domínio.
2. **Domínio testável** — cálculos financeiros em serviços puros, sem dependência de HTTP.
3. **API-first, UI server-rendered** — DRF para futuro mobile; HTMX para velocidade.
   Material 3 + Glassmorphism como camada visual, não como dependência de SPA.
4. **Segurança por padrão** — menor privilégio, TLS, isolamento por usuário.
5. **Observabilidade** — logs estruturados, healthchecks, métricas.
6. **Reprodutibilidade** — Docker, versões fixadas, migrations versionadas.
7. **Evolução incremental** — P1/P2 não exigem reescrita (Open Finance desacoplado).

---

## 2. Visão de contexto (C4 — nível 1)

```mermaid
flowchart LR
    U[Usuário web/mobile] -->|HTTPS| S[Sistema Clareza]
    S -->|SMTP| E[Servidor de e-mail]
    S -.->|P2| OF[Open Finance]
    S -->|backup| BK[Storage de backup]
    A[Operador] -->|SSH/observabilidade| S
```

- **Usuário:** navegador ou PWA.
- **Sistema:** Django + PostgreSQL + Redis.
- **E-mail:** recuperação de senha e lembretes (opt-in).
- **Open Finance:** futuro, via agregador homologado.
- **Backup:** destino externo (S3-compatible, rsync ou volume cifrado).

---

## 3. Containers (C4 — nível 2)

```mermaid
flowchart TB
    subgraph Docker[Docker Compose]
        N[Nginx<br/>TLS, static, reverse proxy]
        W[web<br/>Django + Gunicorn]
        K[worker<br/>Celery]
        B[beat<br/>Celery Beat]
        R[(redis<br/>cache + broker)]
        P[(postgres<br/>dados)]
        M[mailpit dev<br/>SMTP local]
    end
    U[Usuário] -->|443| N
    N --> W
    W --> P
    W --> R
    K --> P
    K --> R
    B --> R
    W -.->|dev| M
    K -.->|dev| M
```

| Serviço | Imagem | Função | Porta |
|---------|--------|--------|-------|
| `web` | build local (Django) | Aplicação HTTP (Gunicorn) | 8000 interno |
| `worker` | mesma imagem | Tarefas assíncronas (Celery) | — |
| `beat` | mesma imagem | Agendador (recorrências, alertas) | — |
| `db` | `postgres:16-alpine` | Banco de dados | 5432 interno |
| `redis` | `redis:7-alpine` | Cache e broker | 6379 interno |
| `nginx` | `nginx:1.27-alpine` | TLS, estáticos, proxy | 80/443 |
| `mailpit` | `axllent/mailpit` | SMTP de desenvolvimento | 8025 (dev) |

**Produção:** `db`, `redis` e `web` sem portas publicadas; apenas `nginx` exposto.
**Dev:** `web` pode expor 8000 para hot reload; `mailpit` para inspecionar e-mails.

---

## 4. Stack e versões

| Camada | Tecnologia | Versão alvo | Justificativa |
|--------|------------|-------------|---------------|
| Linguagem | Python | 3.12+ | Suporte, performance, tipagem |
| Framework | Django | 5.x LTS | Batteries included, segurança, admin |
| API | Django REST Framework | 3.15+ | Contratos e serialização |
| Banco | PostgreSQL | 16 | ACID, tipos numéricos, robustez |
| Cache/Fila | Redis | 7 | Simples, maduro |
| Tarefas | Celery | 5.x | Recorrências e alertas |
| Frontend | Django Templates + HTMX + Alpine.js | atuais | Menos JS, SSR, rápido |
| Componentes UI | `@material/web` (Material 3) | atual | Componentes acessíveis e consistentes |
| CSS | Tailwind CSS + tokens CSS | 3.x/4.x | Layout utilitário + design tokens |
| Estilo | Glassmorphism (camada) | — | Destaque visual com fallback sólido |
| Build frontend | Vite ou esbuild | atual | Bundle self-hosted de Material Web |
| Servidor | Gunicorn | 23+ | WSGI estável |
| Proxy | Nginx | 1.27+ | TLS, estáticos, compressão |
| Testes | pytest + pytest-django + factory_boy | atuais | Produtividade |
| Lint/format | ruff + black + mypy | atuais | Qualidade |
| CI | GitHub Actions | — | Automação |

> Fixar versões exatas em `requirements.txt` / `pyproject.toml` + lockfile
> (pip-tools ou uv). Atualizações passam por CI e changelog.

---

## 5. Organização do código

```
financeiro/
├── Docs/
├── manage.py
├── pyproject.toml
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── nginx.conf
├── compose.yaml
├── compose.dev.yaml
├── .env.example
├── src/
│   ├── config/            # settings, urls, wsgi, asgi, celery
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── accounts/      # User, Profile, consentimentos
│   │   ├── finance/       # categorias, contas, transações, recorrências
│   │   ├── debts/         # dívidas, pagamentos
│   │   ├── plans/         # motor, planos, calendário, cenários e aderência
│   │   ├── reports/       # relatórios e exportações
│   │   ├── notifications/ # preferências, e-mails e lembretes
│   │   └── core/          # shell, health, auditoria, rate limit e headers
│   ├── core/              # base models, mixins, utils, money, dates
│   ├── templates/
│   ├── static/
│   └── locale/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### 5.1 Fronteiras por app

| App | Responsabilidade | Não faz |
|-----|------------------|---------|
| `accounts` | Usuário, perfil, consentimento | Regras financeiras |
| `finance` | Transações, categorias, contas | Cálculo de plano |
| `debts` | Dívidas e pagamentos | Simulação |
| `plans` | Motor, plano, calendário, cenários e aderência | UI e dados financeiros |
| `reports` | Agregações, relatório e exportação | Escrita de negócio |
| `notifications` | Preferências, in-app, e-mail e lembretes | Regras financeiras |
| `core` | Shell, health, auditoria, rate limit e headers | Dados financeiros |

**Regra:** apps não importam modelos uns dos outros diretamente quando possível;
usam serviços e `selectors`. Exceções documentadas.

---

## 6. Camadas

```mermaid
flowchart TB
    V[Views / API Views] --> S[Services]
    V --> Q[Selectors / Queries]
    S --> M[Models]
    Q --> M
    S --> E[Motor de domínio puro]
    M --> DB[(PostgreSQL)]
    S --> T[Celery tasks]
    T --> DB
```

- **Views:** validação de entrada, autorização, orquestração.
- **Services:** transações de negócio, idempotência, auditoria.
- **Selectors:** consultas otimizadas (sem regra de negócio).
- **Motor:** funções puras em `apps/plans/engine/` (sem Django), com tipos e testes.
- **Tasks:** recorrências, alertas, recálculos, exportações.

### 6.1 Motor como biblioteca pura

```python
# apps/plans/engine/types.py (ilustrativo)
@dataclass(frozen=True)
class DebtInput:
    id: str
    balance: Decimal
    monthly_rate: Decimal      # fração, ex.: 0.0199
    minimum_payment: Decimal
    due_day: int

@dataclass(frozen=True)
class PlanInput:
    monthly_available: Decimal
    debts: tuple[DebtInput, ...]
    strategy: str              # avalanche | snowball | hybrid
    start_month: date
    max_months: int = 600
    extra_payment: Decimal = Decimal("0")
```

Benefícios: testável sem banco, reutilizável por CLI/API, determinístico.

---

## 7. Fluxos principais

### 7.1 Geração de plano

```mermaid
sequenceDiagram
    participant U as Usuário
    participant W as Web (Django)
    participant S as PlanService
    participant E as Engine
    participant DB as PostgreSQL
    U->>W: POST /plans (estratégia)
    W->>S: validar e montar input
    S->>DB: carregar dívidas e perfil
    S->>E: simular(input)
    E-->>S: ordem, calendário, totais
    S->>DB: persistir plano + snapshot
    S-->>W: plano
    W-->>U: 201 + calendário
```

### 7.2 Pagamento

```mermaid
sequenceDiagram
    participant U as Usuário
    participant W as Web
    participant S as DebtService
    participant DB as PostgreSQL
    participant C as Celery
    U->>W: POST /debts/{id}/payments (Idempotency-Key)
    W->>S: registrar pagamento
    S->>DB: inserir pagamento (unique key)
    S->>DB: atualizar saldo/status
    S->>DB: marcar plano desatualizado
    S->>C: enfileirar recálculo
    S-->>W: pagamento
    W-->>U: 201
```

### 7.3 Recorrências (Celery Beat)

```
Diariamente 00:10 (America/Sao_Paulo):
  para cada recorrência ativa cuja próxima competência <= hoje:
      criar transação se não existir (unique recorrencia_id + competencia)
      atualizar próxima competência
  enfileirar alertas de vencimento (D-3)
```

**Idempotência:** constraint única `(recurrence_id, competence)`.
**Falha:** retry com backoff; após N tentativas, log de erro e alerta operacional.

### 7.4 Frontend e design system

- **Renderização:** templates Django + HTMX; Alpine.js apenas para estado local.
- **Componentes:** `@material/web` (Material 3), self-hosted e carregado com `defer`.
- **Layout/utilitários:** Tailwind CSS mapeando tokens semânticos.
- **Vidro:** camada CSS própria (`tokens.css`) com `backdrop-filter`, borda e
  fallback sólido; usar no máximo ~8 superfícies por tela.
- **Assets:** Vite/esbuild gera bundle em `static/`; estágio Node no Dockerfile;
  sem CDN em produção. `collectstatic` roda no entrypoint.
- **Fontes/ícones:** Roboto Flex e Material Symbols Rounded, subset e self-hosted.
- **Acessibilidade:** WCAG 2.2 AA, foco visível, `prefers-reduced-motion` e
  `prefers-reduced-transparency`.
- **Fonte da verdade visual:** [11-design-system-material-glass.md](11-design-system-material-glass.md).

---

## 8. Docker

### 8.1 Dockerfile (multi-stage, não-root)

> No repositório, o Dockerfile inclui um estágio `node:22-alpine` que builda
> `@material/web`/Vite antes do estágio Python, garantindo os assets no runtime.

```dockerfile
# docker/Dockerfile (ilustrativo)
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
RUN chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
```

### 8.2 compose.yaml (produção, ilustrativo)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 10
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile
    env_file: .env
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - static:/app/staticfiles
      - media:/app/media
    restart: unless-stopped

  worker:
    build: { context: ., dockerfile: docker/Dockerfile }
    command: ["celery", "-A", "config", "worker", "-l", "INFO", "--concurrency", "2"]
    env_file: .env
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    restart: unless-stopped

  beat:
    build: { context: ., dockerfile: docker/Dockerfile }
    command: ["celery", "-A", "config", "beat", "-l", "INFO"]
    env_file: .env
    depends_on:
      redis: { condition: service_healthy }
    restart: unless-stopped

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - static:/static:ro
      - media:/media:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on: [web]
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
  static:
  media:
```

> **No repositório:** `compose.yaml` contém `db`, `redis`, `web`, `worker` e `beat`.
> O Nginx fica em `compose.prod.yaml` para não ocupar as portas 80/443 em
> desenvolvimento. Produção:
> `docker compose -f compose.yaml -f compose.prod.yaml up -d`.
> Desenvolvimento: `docker compose -f compose.yaml -f compose.dev.yaml up -d`.

### 8.3 compose.dev.yaml (desenvolvimento)

```yaml
services:
  web:
    build: { context: ., dockerfile: docker/Dockerfile.dev }
    command: ["python", "manage.py", "runserver", "0.0.0.0:8000"]
    volumes:
      - .:/app
    ports: ["8000:8000"]
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.dev
  mailpit:
    image: axllent/mailpit
    ports: ["8025:8025", "1025:1025"]
```

**Uso:**

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### 8.4 Entrypoint

```bash
#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py collectstatic --noinput
if [ "${RUN_SEED:-0}" = "1" ]; then python manage.py seed_categories; fi
exec "$@"
```

> Em produção, migrations podem rodar em job separado (one-off) para evitar
> concorrência entre réplicas. No MVP com 1 réplica, o entrypoint é aceitável.

---

## 9. Configuração e ambientes

### 9.1 Variáveis (`.env.example`)

```dotenv
# Django
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=troque-por-valor-aleatorio
DJANGO_ALLOWED_HOSTS=seudominio.com.br,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://seudominio.com.br
DJANGO_DEBUG=0

# Banco
POSTGRES_DB=clareza
POSTGRES_USER=clareza
POSTGRES_PASSWORD=troque
DATABASE_URL=postgresql://clareza:troque@db:5432/clareza

# Redis
REDIS_URL=redis://redis:6379/0

# E-mail
EMAIL_URL=smtp://user:pass@smtp.exemplo.com:587
DEFAULT_FROM_EMAIL=nao-responda@seudominio.com.br

# Segurança
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
SECURE_HSTS_SECONDS=31536000

# Aplicação
APP_TIME_ZONE=America/Sao_Paulo
APP_CURRENCY=BRL
PLAN_ENGINE_VERSION=1
```

### 9.2 Ambientes

| Ambiente | Objetivo | Banco | Dados | TLS |
|----------|----------|-------|-------|-----|
| `dev` | Desenvolvimento local | Docker | Seed/fake | Não |
| `staging` | Homologação | Docker | Anonimizado | Sim (self-signed/LE) |
| `prod` | Produção | Docker | Reais | Sim (Let's Encrypt) |

**Regra:** nunca usar dados reais em `dev`/`staging` sem anonimização.

---

## 10. Segurança de aplicação (resumo)

Detalhes em [08-seguranca-e-lgpd.md](08-seguranca-e-lgpd.md).

- `DEBUG=0` em produção; `ALLOWED_HOSTS` restrito.
- HTTPS obrigatório, HSTS, cookies Secure/HttpOnly/SameSite=Lax.
- CSRF em todos os formulários; DRF com autenticação por sessão e/ou token.
- Senhas com Argon2id; validação contra senhas comuns.
- Rate limit em login, recuperação e endpoints sensíveis.
- Permissões por objeto (`get_queryset` filtrando por usuário).
- Uploads validados (tipo, tamanho) e servidos fora do código.
- Cabeçalhos: CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- Dependências escaneadas em CI (`pip-audit`).
- Segredos apenas em variáveis de ambiente/secret manager.

---

## 11. Observabilidade

### 11.1 Logs

- JSON estruturado: `timestamp`, `level`, `logger`, `request_id`, `user_id_hash`,
  `event`, `duration_ms`, `status`.
- **Nunca** logar valores, credores, e-mails ou tokens.
- Correlação via `X-Request-ID` (gerado no Nginx/Django).

### 11.2 Healthchecks

| Endpoint | Uso | Conteúdo |
|----------|-----|----------|
| `/healthz` | Liveness | 200 se processo vivo |
| `/readyz` | Readiness | 200 se DB e Redis acessíveis |
| `/metrics` (P1) | Prometheus | Latência, erros, fila |

### 11.3 Alertas operacionais (P1)

- Erro 5xx > 1% por 5 min.
- Fila Celery > 1.000 tarefas ou atraso > 10 min.
- Backup falhou ou não executou em 24h.
- Disco > 85%.
- Certificado TLS expira em < 14 dias.

---

## 12. Backup e recuperação

| Item | Política |
|------|----------|
| Banco | `pg_dump` diário comprimido, retenção 30 dias, cópia externa |
| Mídia | Snapshot/rsync diário (se houver uploads) |
| Configuração | `.env` e compose versionados em cofre seguro |
| Criptografia | Backups cifrados em repouso (age/GPG ou storage SSE) |
| Teste de restore | Mensal, em ambiente isolado, com checklist |
| RPO / RTO | 24h / 4h |

**Comando base:**

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip > "backup-$(date +%F).sql.gz"
```

**Restore:**

```bash
gunzip -c backup-2026-11-19.sql.gz \
  | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

> Documentar e testar o restore antes do beta. Backup não testado não é backup.

---

## 13. Testes

| Nível | Ferramenta | Escopo | Meta |
|-------|------------|--------|------|
| Unitário | pytest | Motor, conversões, regras | ≥ 90% no motor |
| Integração | pytest-django | Views, services, banco | ≥ 80% global |
| E2E | Playwright | Fluxos críticos | 8–12 cenários |
| Segurança | pytest + bandit/pip-audit | Authz, CSRF, dependências | Sem crítico |
| Performance | locust/k6 (P1) | P95 de páginas e motor | Metas RNF |

**Casos de ouro do motor** (planilha de referência):

1. 3 dívidas, taxa e saldo distintos — avalanche vs snowball (juros e prazo).
2. Parcela mínima ≤ juros — amortização negativa detectada.
3. Orçamento insuficiente — inviável.
4. Taxa 0 — ordem por saldo.
5. Rollover após quitação — valor redistribuído corretamente.
6. Arredondamento — total de parcelas fecha.
7. Plano > 600 meses — retorno controlado.

**CI (GitHub Actions):**

```yaml
# .github/workflows/ci.yml (ilustrativo)
jobs:
  quality:
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f compose.yaml -f compose.dev.yaml build
      - run: docker compose run --rm web ruff check .
      - run: docker compose run --rm web black --check .
      - run: docker compose run --rm web mypy src
      - run: docker compose run --rm web pytest --cov=src --cov-fail-under=80
      - run: docker compose run --rm web python manage.py check --deploy
```

---

## 14. Deploy

### 14.1 Checklist de produção

- [ ] Domínio e DNS configurados.
- [ ] TLS emitido e renovação automática.
- [ ] `.env` com segredos fortes e `DEBUG=0`.
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` corretos.
- [ ] Migrations aplicadas.
- [ ] `collectstatic` executado.
- [ ] Backup automático agendado e restore testado.
- [ ] Healthchecks verdes.
- [ ] Logs sem PII.
- [ ] Firewall: apenas 80/443 expostos.
- [ ] Atualizações de segurança do host agendadas.

### 14.2 Atualização

```bash
git pull --ff-only
docker compose -f compose.yaml -f compose.prod.yaml build
docker compose -f compose.yaml -f compose.prod.yaml run --rm web \
  python manage.py migrate --noinput
docker compose -f compose.yaml -f compose.prod.yaml up -d
docker compose -f compose.yaml -f compose.prod.yaml exec web \
  python manage.py check --deploy
```

**Estratégia:** janela de manutenção curta, backup antes, rollback por tag de
imagem anterior. Migrations devem ser compatíveis para frente/trás quando possível.

---

## 15. Evolução (P1/P2)

| Evolução | Impacto arquitetural |
|----------|----------------------|
| Importação CSV/OFX | Novo app `imports`, parsers, deduplicação |
| Open Finance | `integrations` com consentimento, tokens cifrados, jobs de sincronização |
| Workspace familiar | `workspace_id` + papéis + regras de visibilidade |
| PWA offline | Service worker, cache, fila de sincronização |
| Notificações push | Web Push + preferências |
| IA assistiva | Serviço isolado, prompts com dados minimizados, opt-in |
| Multimoeda | `currency` por perfil/conta, taxas de câmbio com data |

**Princípio:** novas integrações entram como **adapters**; o núcleo de domínio
não conhece Open Finance nem provedores.

---

## 16. Decisões e trade-offs

| Decisão | Alternativa | Motivo |
|---------|-------------|--------|
| Monólito modular | Microsserviços | Time pequeno, simplicidade, menos latência |
| HTMX + SSR | SPA React | Menos complexidade, entrega rápida, bom SEO no público web |
| Material 3 + glass | UI kit genérico | Consistência, acessibilidade e identidade visual |
| Vidro com fallback | Vidro em tudo | Contraste, legibilidade e performance em devices modestos |
| Celery + Redis | Cron do host | Confiável, retry, observável, portável |
| UUID | BigInt | Segurança/portabilidade, evita enumeração |
| Soft delete | Hard delete | Auditoria e recuperação |
| Plano persistido | Cálculo on-the-fly | Reprodutibilidade e histórico |
| Motor puro | Lógica nos models | Testabilidade e clareza |

ADRs detalhados em [10-adr-decisoes-arquiteturais.md](10-adr-decisoes-arquiteturais.md).
