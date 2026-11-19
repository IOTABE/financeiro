# 08 — Segurança, Privacidade e LGPD

**Objetivo:** definir controles de segurança e conformidade para proteger dados
financeiros, orientar a implementação e preparar o produto para operação
responsável no Brasil.

**Escopo:** aplicação, banco, infraestrutura Docker, backups, operação e ciclo
de desenvolvimento.

> **Implementado na Fase 4:** CSP e headers, rate limit em login/registro/reset,
> `AuditLog`, exportação/exclusão em "Meus dados", `bandit` e `pip-audit` no CI.

---

## 1. Princípios

1. **Privacidade por padrão e por design.** Coletar o mínimo, com finalidade clara.
2. **Menor privilégio.** Pessoas e serviços acessam apenas o necessário.
3. **Defesa em profundidade.** Camadas independentes de proteção.
4. **Segurança verificável.** Controles testados, não apenas documentados.
5. **Transparência.** O titular entende o que é coletado e por quê.
6. **Responsabilização.** Registros de decisões, auditoria e resposta a incidentes.
7. **Ética.** Não vender dados, não manipular vulnerabilidade, não prometer crédito.

---

## 2. Classificação de dados

| Categoria | Exemplos | Sensibilidade | Controles |
|-----------|----------|---------------|-----------|
| **Credenciais** | Senha, token, segredo | Crítica | Hash Argon2id, cofre, nunca logar |
| **Dados financeiros** | Renda, dívidas, transações, saldos | Alta | TLS, criptografia em repouso, acesso restrito, auditoria |
| **Dados pessoais** | Nome, e-mail, dependentes | Média | Mineração, TLS, acesso restrito |
| **Metadados de segurança** | IP, user-agent, logs de acesso | Média | Hash quando possível, retenção limitada |
| **Auditoria** | Eventos de conta e alterações | Média | Append-only, sem valores, retenção definida |
| **Telemetria** | Eventos agregados | Baixa | Opt-in, anonimizada |

> A LGPD não classifica dados financeiros como "sensíveis" no art. 5º, II, mas
> eles são de **alta sensibilidade contextual** e exigem proteção reforçada.

---

## 3. Bases legais e finalidades (LGPD)

| Tratamento | Base legal | Finalidade | Retenção |
|------------|------------|------------|----------|
| Cadastro e autenticação | Execução de contrato (art. 7º, V) | Acesso ao serviço | Enquanto a conta existir |
| Registro de receitas/despesas/dívidas | Execução de contrato | Funcionalidade principal | Enquanto a conta existir |
| Plano e simulações | Execução de contrato | Funcionalidade principal | Enquanto a conta existir |
| E-mails transacionais | Execução de contrato / legítimo interesse | Segurança e operação | 6 meses (logs de envio) |
| Lembretes e resumo | Consentimento (art. 7º, I) | Comunicação | Até revogação |
| Telemetria | Consentimento | Melhoria do produto | 12 meses (agregada) |
| Auditoria de segurança | Obrigação legal / legítimo interesse (art. 7º, II/IX) | Prevenção a fraude | 5 anos (ou política) |
| Backups | Execução de contrato / segurança | Recuperação | 30 dias |

**Minimização:** não coletar CPF, endereço, dados bancários completos ou número
de cartão. O app não move dinheiro; não precisa desses dados.

**Consentimento:** granular, registrado com versão, data/hora e hash de IP/UA.
Revogável a qualquer momento; a revogação não afeta tratamentos por outras bases.

---

## 4. Direitos do titular e como atendê-los

| Direito (LGPD art. 18) | Implementação |
|------------------------|---------------|
| Confirmação e acesso | Tela "Meus dados" + exportação |
| Correção | Edição no app; suporte para casos específicos |
| Anonimização/bloqueio/eliminação | Exclusão de conta; anonimização de logs |
| Portabilidade | Exportação JSON/CSV completa |
| Informação sobre compartilhamento | Não há compartilhamento no MVP |
| Revogação de consentimento | Preferências de comunicação e telemetria |
| Oposição | Canal de contato e análise |
| Petição à ANPD | Informação no canal de privacidade |

**Prazos:** responder em até 15 dias (boas práticas); exclusão efetiva em até 30
dias, ressalvadas obrigações legais e backups (documentar).

---

## 5. Modelo de ameaças (STRIDE)

| Ameaça | Cenário | Controles |
|--------|---------|-----------|
| **Spoofing** | Roubo de senha/sessão | Argon2id, MFA (P1), cookies seguros, rate limit, detecção de login anômalo |
| **Tampering** | Alteração de transações/pagamentos | Autorização por objeto, CSRF, auditoria, validação server-side, integridade de migrations |
| **Repudiation** | Usuário nega ação | Auditoria append-only com timestamp e request_id |
| **Information disclosure** | Vazamento entre usuários ou em logs | Isolamento por user_id, testes de acesso cruzado, logs sem PII, TLS, criptografia |
| **Denial of service** | Esgotar recursos | Rate limit, limites de payload, timeouts, limites de simulação, proxy |
| **Elevation of privilege** | Acessar admin/dados de terceiros | RBAC, admin separado, sem impersonação por padrão, menor privilégio no banco |
| **Supply chain** | Dependência comprometida | Lockfile, pip-audit, imagens oficiais, build reproduzível, revisão |

### 5.1 Superfícies de ataque

- Login e recuperação de senha.
- Formulários e API (entrada de valores, datas, IDs).
- Upload de arquivos (P1): tipo, tamanho, conteúdo, path traversal.
- Painel admin do Django (restringir por IP/VPN ou desabilitar em produção).
- Container e host (portas, SSH, atualizações).
- Backups (acesso e criptografia).
- Integrações futuras (Open Finance): tokens e consentimentos.

### 5.2 Atores

- Atacante externo oportunista.
- Usuário autenticado tentando acessar dados de outro.
- Insider/operador com acesso ao host.
- Dependência ou imagem comprometida.

---

## 6. Controles de segurança

### 6.1 Autenticação

- Senhas com Argon2id (parâmetros recomendados pela OWASP), mínimo 10 caracteres,
  bloqueio de senhas comuns e vazadas (k-anonymity, se viável).
- Rate limit e atraso progressivo em falhas.
- Sessões com rotação no login, expiração por inatividade (padrão 60 min),
  invalidação no logout e na troca de senha.
- MFA TOTP (P1) com códigos de recuperação.
- Recuperação por token de uso único, expiração 30 min, sem revelar existência
  de e-mail.
- E-mail de alerta em novos logins (P1).

### 6.2 Autorização

- Toda consulta filtra por `user_id` (ou workspace no P1).
- `get_queryset` e `get_object` sempre escopados; nunca confiar em ID do cliente.
- Acesso a recurso de outro usuário retorna **404** (não 403) para não vazar existência.
- Testes automatizados de acesso cruzado em todos os endpoints.
- Admin do Django: `is_staff` restrito, 2FA, acesso por VPN/IP allowlist.

### 6.3 Validação de entrada

- Serializers DRF + validações de domínio.
- Limites: valor máximo, número de parcelas, tamanho de texto, dias válidos.
- Nunca interpolar entrada em SQL; usar ORM/parametrização.
- Escapar saída em templates (Django autoescape).
- Uploads (P1): whitelist de MIME/extensão, tamanho máximo, varredura, nomes aleatórios,
  armazenamento fora do webroot e `Content-Disposition: attachment`.
- Proteção contra CSV injection na exportação (prefixar células que começam com
  `=`, `+`, `-`, `@`).

### 6.4 Proteções web

| Controle | Configuração |
|----------|--------------|
| HTTPS | Redirect + HSTS (1 ano, subdomínios) |
| Cookies | `Secure`, `HttpOnly`, `SameSite=Lax` |
| CSRF | Middleware ativo; token em formulários e API de sessão |
| CSP | `default-src 'self'`; ajustar para CDN se houver |
| X-Frame-Options | `DENY` |
| X-Content-Type-Options | `nosniff` |
| Referrer-Policy | `strict-origin-when-cross-origin` |
| Permissions-Policy | Desabilitar câmera/mic/geolocalização |
| CORS | Sem CORS aberto; apenas origens explícitas (API mobile P1) |

### 6.5 Sessão e CSRF

- Sessões no banco/Redis, com rotação e expiração.
- `CSRF_TRUSTED_ORIGINS` restrito ao domínio.
- Requisições mutáveis exigem CSRF (web) ou Bearer token (API P1).
- Reautenticação para ações sensíveis (exclusão de conta, exportação).

### 6.6 Criptografia

| Camada | Controle |
|--------|----------|
| Transporte | TLS 1.2+ (preferir 1.3), certificado válido, renovação automática |
| Banco | Criptografia de disco/volume (LUKS, EBS encryption) |
| Backups | Criptografia em repouso (age/GPG ou SSE) |
| Segredos | Variáveis de ambiente/secret manager; nunca no Git |
| Senhas | Argon2id |
| Tokens (P1/P2) | Hash no banco; tokens de terceiros cifrados com chave gerenciada |

**Não** implementar criptografia caseira. Usar bibliotecas consolidadas.

### 6.7 Segredos

- `.env` fora do Git; `.env.example` sem valores reais.
- Rotação de `SECRET_KEY`, senhas de banco e tokens.
- Acesso ao host restrito; chaves SSH com passphrase.
- Nunca logar segredos; mascarar em mensagens de erro.
- CI usa secrets do repositório, com escopo mínimo.

### 6.8 Infraestrutura Docker

- Imagens oficiais e versões fixadas (digest quando possível).
- Container não-root; filesystem read-only quando viável; `no-new-privileges`.
- Apenas 80/443 expostos; DB/Redis sem portas públicas.
- Healthchecks e restart policies.
- Limites de CPU/memória (P1).
- Scan de imagem (Trivy/Grype) em CI.
- Host atualizado, firewall, SSH por chave, fail2ban (recomendado).
- Logs de container sem PII.

### 6.9 Banco de dados

- Usuário de aplicação sem superuser; permissões mínimas.
- Conexões TLS quando fora do host Docker.
- Backup criptografado e restore testado.
- Sem `SELECT *` em produção; sem acesso direto de terceiros.
- Migrations revisadas; sem dados sensíveis em fixtures.

### 6.10 Logs e monitoramento

- Logs estruturados, sem valores, credores, e-mails ou tokens.
- `user_id` apenas como hash/UUID interno quando necessário.
- Retenção de logs de aplicação: 30–90 dias.
- Alertas para: picos de 401/403, rate limit, erros 5xx, falha de backup,
  criação/exclusão anômala de dados, acesso admin.

---

## 7. LGPD na prática

### 7.1 Transparência

- Política de privacidade em linguagem clara, versionada.
- Aviso no onboarding: o que é coletado, por quê, por quanto tempo.
- "Meus dados": visão, exportação e exclusão.
- Canal de privacidade (e-mail/encarregado).

### 7.2 Encarregado (DPO)

- Indicar encarregado e canal de contato (obrigação legal quando aplicável).
- Publicar identidade e contato.
- Registrar solicitações e prazos.

### 7.3 Registro de operações (ROPA)

Manter inventário de tratamentos:

| Campo | Exemplo |
|-------|---------|
| Finalidade | Gerar plano de regularização |
| Dados | Renda, dívidas, transações |
| Titulares | Usuários |
| Bases legais | Execução de contrato |
| Compartilhamento | Nenhum (MVP) |
| Retenção | Enquanto a conta existir |
| Medidas | TLS, criptografia, acesso restrito |

### 7.4 Avaliação de impacto (RIPD)

Recomendada antes do beta público, dado o volume de dados financeiros.
Abordar: necessidade/proporcionalidade, riscos, mitigação, consulta a titulares.

### 7.5 Incidentes

**Fluxo:**

1. **Detectar** (alerta, relato, auditoria).
2. **Conter** (revogar credenciais, isolar serviço, bloquear acesso).
3. **Avaliar** escopo, dados afetados, risco aos titulares.
4. **Notificar** ANPD e titulares quando houver risco relevante (prazo legal).
5. **Corrigir** causa raiz e adicionar controles.
6. **Documentar** postmortem sem dados pessoais.

**Registro:** data/hora, descoberta, causa, dados, titulares, medidas, comunicação.

### 7.6 Suboperadores

- Evitar terceiros no MVP.
- Se houver (e-mail, backup, hospedagem), formalizar contrato com cláusulas LGPD,
  due diligence e lista pública.

### 7.7 Transferência internacional

- Preferir provedores no Brasil ou com garantias adequadas.
- Documentar base legal e salvaguardas.

---

## 8. Retenção e descarte

| Dado | Retenção | Descarte |
|------|----------|----------|
| Conta e dados financeiros | Enquanto ativa | Exclusão/anonimização em até 30 dias |
| Backups | 30 dias | Expiração automática |
| Logs de aplicação | 30–90 dias | Rotação |
| Auditoria | 5 anos (ou política) | Anonimização de `user_id` |
| Consentimentos | Enquanto a conta existir + prazo legal | Arquivamento |
| Telemetria | 12 meses | Agregação/anonimização |
| Arquivos importados (P1) | Até processamento | Remoção imediata |
| E-mails enviados | 6 meses | Expiração |

**Exclusão de conta:** remover/anonimizar dados, invalidar sessões, revogar tokens,
manter apenas registros exigidos por lei (sem possibilidade de reidentificação).

---

## 9. Segurança no ciclo de desenvolvimento (SSDLC)

- Revisão de código obrigatória; checklist de segurança no PR.
- Testes automatizados de autorização e validação.
- `pip-audit`/`bandit`/`ruff` no CI.
- Scan de imagem (Trivy) e de segredos (gitleaks).
- Dependências fixadas; atualização mensal com changelog.
- Threat modeling a cada nova integração (Open Finance, uploads).
- Pentest antes de beta público (escopo: auth, authz, IDOR, injeção, CSRF, rate limit).
- Ambiente de staging separado, sem dados reais.

### 9.1 Checklist de PR sensível

- [ ] Consulta filtra por usuário.
- [ ] Entrada validada no servidor.
- [ ] Nenhum segredo/PII em log.
- [ ] CSRF/autorização corretos.
- [ ] Teste de acesso cruzado.
- [ ] Migração reversível ou plano de rollback.
- [ ] Dependência nova justificada e auditada.

---

## 10. Backups e continuidade

| Item | Política |
|------|----------|
| Frequência | Diária (banco), semanal (mídia) |
| Retenção | 30 dias |
| Criptografia | Obrigatória |
| Local | Externo ao host principal |
| Teste de restore | Mensal |
| RPO/RTO | 24h / 4h |
| Acesso | Restrito, auditado |

**Não** armazenar backups no mesmo volume do banco. **Não** versionar dumps no Git.

---

## 11. Resposta a incidentes (runbook resumido)

1. **Classificar** severidade (S1 crítico: vazamento/dados; S2 alto: indisponibilidade;
   S3 médio: funcional; S4 baixo).
2. **Acionar** responsáveis (produto, engenharia, segurança, jurídico).
3. **Conter** e preservar evidências (logs, snapshots).
4. **Comunicar** internamente e, se aplicável, ANPD/titulares.
5. **Erradicar** e recuperar com backup validado.
6. **Pós-incidente:** postmortem blameless, ações com prazo e dono.

**Contatos:** definir em documento operacional privado (não neste repositório).

---

## 12. Avisos legais e ética

- O app **não** é instituição financeira, consultoria de investimentos ou
  assessoria jurídica.
- Não promete aprovação de crédito, desconto ou resultado de negociação.
- Simulações são estimativas baseadas em dados informados pelo usuário.
- Casos de superendividamento podem ser tratados nos termos da Lei nº 14.181/2021;
  o app informa e educa, sem substituir profissional habilitado.
- Linguagem acolhedora, sem discriminação, sem exploração de vulnerabilidade.
- Sem venda, aluguel ou compartilhamento de dados pessoais.

---

## 13. Checklist de conformidade (MVP)

### Segurança
- [ ] TLS obrigatório e HSTS.
- [ ] Senhas Argon2id e política mínima.
- [ ] CSRF, cookies seguros, CSP.
- [ ] Isolamento por usuário testado.
- [ ] Rate limit em auth e endpoints sensíveis.
- [ ] Admin restrito e com 2FA.
- [ ] Logs sem PII.
- [ ] Dependências e imagens escaneadas.
- [ ] Backups cifrados e restore testado.
- [ ] Pentest antes do beta público.

### LGPD
- [ ] Política de privacidade publicada e versionada.
- [ ] Termos de uso publicados.
- [ ] Consentimentos registrados.
- [ ] Exportação e exclusão funcionando.
- [ ] Encarregado e canal definidos.
- [ ] ROPA preenchido.
- [ ] Retenção e descarte implementados.
- [ ] Runbook de incidentes.
- [ ] Sem compartilhamento não divulgado.
- [ ] RIPD antes do beta público.

### Operação
- [ ] Firewall e SSH por chave.
- [ ] Apenas 80/443 expostos.
- [ ] Atualizações agendadas.
- [ ] Monitoramento e alertas.
- [ ] Documentação de deploy e restore.
- [ ] Contatos de emergência definidos.
