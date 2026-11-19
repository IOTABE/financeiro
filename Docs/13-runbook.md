# 13 — Runbook de Desenvolvimento e Operação

**Objetivo:** permitir que qualquer pessoa suba, valide, atualize e recupere o
ambiente sem depender de conhecimento tribal.

**Status:** Fase 1 validada (Docker, auth, perfil, design base, testes).
**Última atualização:** 2026-11-19

---

## 1. Pré-requisitos

| Ferramenta | Versão mínima |
|------------|---------------|
| Docker | 24+ |
| Docker Compose | v2 |
| Git | 2.30+ |
| Python (opcional, fora do container) | 3.12+ |
| Node.js (opcional, para assets Material) | 20+ |

---

## 2. Primeira execução (desenvolvimento)

```bash
cp .env.example .env
# Edite o .env se necessário (o compose.dev já força settings de dev)
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

Verifique:

```bash
docker compose -f compose.yaml -f compose.dev.yaml ps
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
```

Acesse:

- Aplicação: <http://localhost:8000>
- Design system: <http://localhost:8000/estilo/>
- Mailpit (e-mails de dev): <http://localhost:8025>
- Admin: <http://localhost:8000/admin/> (crie um superusuário)

### Criar superusuário

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec web \
  python manage.py createsuperuser
```

### Rodar migrações manualmente

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec web \
  python manage.py migrate
```

> O entrypoint já roda `migrate` e `collectstatic` ao iniciar o `web`.
> `worker` e `beat` não rodam migrations (entrypoint vazio).

---

## 3. Comandos do dia a dia

```bash
# Subir
docker compose -f compose.yaml -f compose.dev.yaml up -d

# Logs
docker compose -f compose.yaml -f compose.dev.yaml logs -f web

# Shell Django
docker compose -f compose.yaml -f compose.dev.yaml exec web python manage.py shell

# Testes
docker compose -f compose.yaml -f compose.dev.yaml exec web pytest
# alternativa sem pytest:
docker compose -f compose.yaml -f compose.dev.yaml exec web python manage.py test

# Lint / format
docker compose -f compose.yaml -f compose.dev.yaml exec web ruff check .
docker compose -f compose.yaml -f compose.dev.yaml exec web black --check .

# Materializar recorrências até hoje
docker compose -f compose.yaml -f compose.dev.yaml exec web \
  python manage.py run_recurrences

# Criar/recriar usuário de demonstração
docker compose -f compose.yaml -f compose.dev.yaml exec web \
  python manage.py seed_demo --email demo@clareza.local --reset

# Gerar lembretes de vencimento (também roda no Celery Beat)
docker compose -f compose.yaml -f compose.dev.yaml exec web \
  python manage.py send_due_reminders

# Parar
docker compose -f compose.yaml -f compose.dev.yaml down

# Parar e apagar volumes (CUIDADO: apaga banco)
docker compose -f compose.yaml -f compose.dev.yaml down -v
```

### Ambiente local sem Docker (opcional)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

O settings padrão do `manage.py` é `config.settings.dev` com SQLite. Para usar
PostgreSQL, defina `DATABASE_URL`.

---

## 4. Assets (Material Web + Tailwind)

O CSS base (`tokens.css` + `app.css`) funciona sem build. Para habilitar os
componentes Material Web:

```bash
npm install
npm run build
```

Saída em `src/static/vendor/material.js`. No Docker de produção, o bundle é
gerado automaticamente por um estágio Node no `docker/Dockerfile`. Para carregar
no template, adicione `{% static 'vendor/material.js' %}` no bloco `extra_js`
quando o bundle existir. Sem o bundle, os componentes nativos estilizados
continuam funcionando (progressive enhancement).

---

## 5. Produção (Docker Compose)

```bash
cp .env.example .env
# Edite: DJANGO_SETTINGS_MODULE=config.settings.prod, DJANGO_SECRET_KEY,
# DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS, POSTGRES_*, EMAIL_*,
# SECURE_SSL_REDIRECT=1, SESSION_COOKIE_SECURE=1, CSRF_COOKIE_SECURE=1.

docker compose -f compose.yaml -f compose.prod.yaml build
docker compose -f compose.yaml -f compose.prod.yaml run --rm web \
  python manage.py migrate --noinput
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

> O `compose.prod.yaml` adiciona o Nginx (portas 80/443) e volumes de estáticos.
> Configure TLS (Let's Encrypt/certbot) e o `docker/nginx.conf` antes de expor.

### Checklist mínimo

- [ ] `DJANGO_SECRET_KEY` forte e exclusivo.
- [ ] `DJANGO_ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` corretos.
- [ ] PostgreSQL acessível apenas na rede interna.
- [ ] TLS ativo e HSTS configurado.
- [ ] `python manage.py check --deploy` sem issues.
- [ ] Backup automático agendado e restore testado.
- [ ] Logs sem PII.
- [ ] Admin restrito (VPN/IP allowlist ou desabilitado).

---

## 6. Banco de dados

### Backup

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip > "backup-$(date +%F-%H%M).sql.gz"
```

### Restore

```bash
gunzip -c backup-2026-11-19-1530.sql.gz \
  | docker compose -f compose.yaml -f compose.prod.yaml exec -T db \
      psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

> Teste o restore em ambiente isolado antes de confiar no backup.

---

## 7. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `permission denied` no entrypoint | script sem bit de execução | `chmod +x docker/entrypoint.sh` |
| Worker reiniciando com `VersionMismatch` | `redis-py` antigo | Garanta `redis>=6.1,<7` e rebuild |
| `readyz` 503 | DB/Redis indisponível | Ver logs de `db`/`redis` e healthchecks |
| Estáticos 404 | `collectstatic` não rodou | `docker compose exec web python manage.py collectstatic` |
| Migrations pendentes | container subiu sem entrypoint | `docker compose exec web python manage.py migrate` |
| Porta 8000 ocupada | outro processo/container | `docker compose down` ou mude a porta |
| E-mail não chega em dev | Mailpit não está aberto | Ver <http://localhost:8025> |
| `check --deploy` com warnings | usando settings de dev | Rode com `DJANGO_SETTINGS_MODULE=config.settings.prod` e envs de produção |

---

## 8. Testes e qualidade

```bash
.venv/bin/ruff check .
.venv/bin/black --check .
.venv/bin/python manage.py test
DJANGO_SETTINGS_MODULE=config.settings.prod \
DJANGO_SECRET_KEY='...' DJANGO_ALLOWED_HOSTS='example.com' \
DJANGO_CSRF_TRUSTED_ORIGINS='https://example.com' \
DATABASE_URL='postgresql://user:pass@localhost:5432/db' \
PYTHONPATH=src .venv/bin/python manage.py check --deploy
```

**Estado atual:** 87 testes verdes, `ruff`/`black` limpos, `check --deploy`
sem issues com settings de produção.

---

## 9. Segurança operacional

- Nunca commitar `.env` ou dumps.
- Rotacionar `DJANGO_SECRET_KEY`, senha do banco e credenciais de e-mail.
- Apenas 80/443 expostos em produção.
- SSH por chave; firewall ativo; atualizações do host agendadas.
- Monitorar: 5xx, fila Celery, falha de backup, disco, expiração de TLS.
- Administrar usuários e permissões com menor privilégio.
- Seguir o runbook de incidentes em [08-seguranca-e-lgpd.md](08-seguranca-e-lgpd.md).

---

## 10. Estado atual

| Item | Status |
|------|--------|
| Docker Compose (dev) | ✅ validado (web, db, redis, worker, beat, mailpit) |
| Healthchecks | ✅ `/healthz` e `/readyz` 200 |
| Auth e perfil | ✅ testes |
| Categorias e contas | ✅ CRUD, seeds e arquivamento |
| Transações | ✅ CRUD, filtros, parcelamento e soft delete |
| Recorrências | ✅ materialização idempotente + task Celery |
| Dívidas e pagamentos | ✅ CRUD, juros/principal e idempotência |
| Motor e plano | ✅ casos de ouro, snapshot, calendário e stale |
| Comparação e simulador | ✅ avalanche/snowball/híbrida + cenários |
| Aderência | ✅ marcar parcelas planejadas como pagas |
| Relatórios | ✅ relatório mensal + exportação JSON/CSV |
| Notificações | ✅ preferências, in-app, e-mail e dedupe |
| Meus dados/LGPD | ✅ exportação e exclusão auditada |
| Hardening | ✅ CSP, rate limit, headers e auditoria |
| Dashboard e onboarding | ✅ indicadores reais, plano e checklist |
| Design system base | ✅ tokens, glass, style guide |
| Testes | ✅ 87 verdes |
| Lint/format | ✅ ruff/black limpos |
| `check --deploy` | ✅ sem issues (settings prod) |
| Assets Material Web | ✅ bundle Vite gerado no Docker |
| Segurança | ✅ bandit e pip-audit limpos; pentest externo pendente |
| Beta | ⏳ `seed_demo` e checklist prontos; usuários a convidar |

**Próxima fase:** beta fechado (10–20 usuários), feedback e pentest externo.

---

## 11. Checklist do beta fechado

### Preparação
- [ ] Criar ambiente de staging com dados anonimizados.
- [ ] Rodar `seed_demo` para validar o fluxo completo.
- [ ] Revisar política de privacidade e termos com apoio jurídico.
- [ ] Definir canal de suporte e horário de resposta.
- [ ] Configurar SMTP real e testar entrega (SPF/DKIM/DMARC).
- [ ] Confirmar backup automático e restore testado.
- [ ] Revisar logs sem PII e alertas operacionais.

### Convocação
- [ ] Recrutar 10–20 usuários do perfil-alvo.
- [ ] Explicar o escopo do beta e o disclaimer (não é consultoria).
- [ ] Coletar consentimento para participação e feedback.
- [ ] Definir métricas: ativação, plano gerado, aderência, retenção e NPS.

### Operação
- [ ] Acompanhar erros 5xx, fila Celery e falhas de e-mail.
- [ ] Revisar feedback semanalmente e priorizar correções.
- [ ] Não alterar escopo durante o beta sem registro em ADR.
- [ ] Realizar pentest externo antes de abrir para o público.
- [ ] Revisar RIPD/ROPA com os dados e riscos observados.

### Critérios para beta público
- [ ] Nenhum achado crítico de segurança.
- [ ] Fluxo completo estável por 2 semanas.
- [ ] Aderência ≥ 40% e NPS ≥ 40 no beta.
- [ ] Backup/restore e resposta a incidentes validados.
