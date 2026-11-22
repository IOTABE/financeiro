# 14 — Importação de Extratos Bancários (OFX)

**Objetivo:** descrever o passo a passo da importação de extratos bancários em
formato OFX, incluindo o fluxo funcional (UX), o fluxo técnico, a categorização
assistida com reaproveitamento de regras e a deduplicação.

**Status:** Fase 1 implementada (OFX). Fase 2 (PDF) esboçada, não implementada.
**Última atualização:** 2026-11-22

---

## 1. Visão geral

A importação transforma um extrato bancário OFX em lançamentos (`Transaction`)
no app, sem exigir digitação manual. O fluxo tem quatro etapas:

1. **Upload** do arquivo `.ofx` e escolha da conta de destino.
2. **Pré-visualização** dos lançamentos detectados.
3. **Categorização** dos itens ainda sem categoria.
4. **Confirmação** — grava as transações e aprende as categorias escolhidas.

A grande vantagem é o **aprendizado**: ao categorizar um lançamento, o sistema
cria uma regra (`CategoryRule`) que categoriza automaticamente lançamentos com a
mesma descrição nos próximos extratos.

---

## 2. Passo a passo funcional (UX)

### 2.1 Acessar a importação

Em **Transações**, clique em **"Importar extrato"** (ao lado de "Compra parcelada").

- Rota: `GET /financeira/transacoes/importar/` (`finance:import_start`).

### 2.2 Enviar o arquivo

1. Selecione o arquivo `.ofx` (ex.: `NU_75126747_01JAN2026_31JAN2026.ofx`).
2. Escolha a **conta** de destino (padrão: "Conta principal").
3. Clique em **"Continuar"**.

- Se o arquivo não terminar em `.ofx`, o formulário exibe
  *"Envie um arquivo no formato OFX (.ofx)."*.
- Se o conteúdo for inválido, exibe *"Não foi possível ler o arquivo OFX."*.

### 2.3 Revisar a pré-visualização

A tela lista os lançamentos detectados com **Data**, **Descrição**, **Valor**,
**Categoria** e **Status**. Cada linha pode ter um de três estados:

| Estado | Explicação | Ação do usuário |
|--------|-----------|-----------------|
| **Automático** | A descrição já tem regra cadastrada | Nenhuma (categoria pré-selecionada) |
| **Requer categoria** | Sem regra; categoria vazia | Escolher no seletor |
| **Ignorado** | Lançamento já importado antes | Nenhuma (desabilitado) |

- Rota: `GET /financeira/transacoes/importar/preview/` (`finance:import_preview`).

### 2.4 Confirmar

Clique em **"Confirmar importação"**. O sistema grava os lançamentos e mostra o
resumo: *"Importação concluída: N lançamento(s) criado(s)."* (e, se houver,
*"M lançamento(s) ignorado(s) por já existirem."*).

- Rota: `POST /financeira/transacoes/importar/confirmar/` (`finance:import_confirm`).

---

## 3. Passo a passo técnico

### 3.1 Parser (`apps/finance/importers.py`)

`parse_ofx(content: bytes) -> ParsedStatement`:

1. Remove espaços iniciais e, se o arquivo não começar com `OFXHEADER:`, injeta
   um header padrão com `ENCODING:UTF-8` (necessário para o `ofxparse` decodificar
   acentos).
2. Delega ao `ofxparse.OfxParser.parse` sobre um `io.BytesIO`.
3. Para cada `STMTTRN`, produz um `ParsedTransaction`:
   - **tipo** (`kind`): pelo sinal de `TRNAMT` — `≥ 0` → `income`, `< 0` → `expense`;
   - **valor** (`amount`): `abs(TRNAMT)`;
   - **data** (`transaction_date`): de `DTPOSTED`;
   - **descrição** (`description`): de `MEMO`;
   - **identificador** (`fitid`): de `FITID`.
4. Retorna também `account_id` (o `ACCTID` do banco, ex.: `7512674-7`).

`normalize_description(value)` normaliza a descrição para casar regras:
minúsculas, `strip`, espaços colapsados — ex.: `"  Pagamento   DE Fatura "` →
`"pagamento de fatura"`.

`idempotency_key(account_id, fitid)` → `f"ofx:{account_id}:{fitid}"`.

### 3.2 Serialização na sessão

O resultado do parse é armazenado na sessão (`request.session["import_data"]`)
para sobreviver ao redirecionamento upload → preview → confirm:

```json
{
  "account_id": "<pk da Conta destino>",
  "source_account_id": "7512674-7",
  "transactions": [
    {"kind": "expense", "amount": "50.13", "transaction_date": "2026-01-02",
     "description": "Pagamento de fatura", "fitid": "fit-1"}
  ]
}
```

`Decimal` e `date` são serializados como string/ISO e reconstruídos nas views
via `_deserialize_import`.

### 3.3 Pré-visualização (`services.build_import_preview`)

Para cada lançamento do extrato:

1. Calcula `pattern = normalize_description(description)`.
2. Busca `CategoryRule` por `(user, kind, pattern)`; se existir, pré-seleciona a
   categoria.
3. Verifica se `idempotency_key` já existe → marca `duplicate`.

### 3.4 Aplicação (`services.apply_import`)

Dentro de `transaction.atomic()`, para cada linha:

1. Monta `idempotency_key`; se já existe `Transaction` com essa chave, **pula**
   (incrementa `skipped`).
2. Se o item tem categoria escolhida:
   - resolve a `Category` (validando `user`);
   - `CategoryRule.update_or_create(user, kind, pattern, defaults={"category": ...})`.
3. Cria a `Transaction` com `status=PAID`, `paid_at=transaction_date` e
   `idempotency_key`.

Retorna `(created, skipped)`.

---

## 4. Modelo de dados — `CategoryRule`

`apps/finance/models.py`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | PK |
| `user` | FK `User` | Dono da regra |
| `kind` | `income`/`expense` | Tipo do lançamento |
| `pattern` | VARCHAR(200) | Descrição normalizada |
| `category` | FK `Category` | Categoria alvo (`on_delete=CASCADE`) |
| `created_at`/`updated_at` | TIMESTAMPTZ | — |

**Constraints/índices:**

- `UniqueConstraint(user, kind, pattern)` — `uq_import_rule_user_kind_pattern`.
- `Index(user, kind, pattern)`.

Migration: `finance/0002_categoryrule.py`.

---

## 5. Deduplicação e idempotência

A deduplicação reusa o constraint existente `uq_transaction_user_idempotency`
(`user`, `idempotency_key`). A chave `ofx:{account_id}:{fitid}` garante que:

- Importar o mesmo arquivo duas vezes não cria duplicatas (os itens aparecem como
  "Ignorado" na pré-visualização).
- Extratos de contas diferentes não colidem (o `account_id` entra na chave).

> O `FITID` é o identificador único que o banco atribui a cada lançamento no OFX;
> por isso é a base natural da idempotência.

---

## 6. Regras de negócio e casos de borda

- **RN-IMP-01** — Tipo pelo sinal do valor: `+` é receita, `−` é despesa.
- **RN-IMP-02** — Lançamento importado nasce como **Pago** (`status=PAID`,
  `paid_at=transaction_date`), pois já consta no extrato.
- **RN-IMP-03** — A competência (`competence_month`) é derivada automaticamente
  pela data (via `Transaction.save`).
- **RN-IMP-04** — Regra só é criada quando o usuário efetivamente escolhe uma
  categoria; itens deixados "Sem categoria" não geram regra.
- **RN-IMP-05** — Categorizar de novo um padrão já existente atualiza a regra
  (a última escolha vence).
- **RN-IMP-06** — Arquivo sem lançamentos → *"O extrato não contém lançamentos."*.
- **RN-IMP-07** — Extratos de formato inesperado não quebram a importação; geram
  mensagem amigável e mantêm o usuário na tela de upload.

---

## 7. Arquivos envolvidos

| Arquivo | Papel |
|---------|-------|
| `src/apps/finance/importers.py` | Parser OFX, normalização, chave de idempotência |
| `src/apps/finance/models.py` | Modelo `CategoryRule` |
| `src/apps/finance/services.py` | `build_import_preview`, `apply_import` |
| `src/apps/finance/forms.py` | `ImportForm` (upload + conta) |
| `src/apps/finance/views.py` | `import_start`, `import_preview`, `import_confirm` |
| `src/apps/finance/urls.py` | Rotas de importação |
| `src/apps/finance/templates/finance/import_form.html` | Tela de upload |
| `src/apps/finance/templates/finance/import_preview.html` | Tela de revisão |
| `tests/test_import.py` | Testes do fluxo completo |
| `pyproject.toml` / `requirements/base.txt` | Dependência `ofxparse` |

---

## 8. Testes

`tests/test_import.py` cobre:

- Parser: valores, datas, tipo por sinal e `account_id`.
- Normalização da descrição.
- `apply_import`: criação de transações + regra; idempotência (2ª importação = 0 criados).
- `build_import_preview`: regra existente aplicada e duplicado sinalizado.
- Fluxo de views: upload → preview → confirm; rejeição de arquivo não-OFX.

Comandos:

```bash
.venv/bin/python -m pytest tests/test_import.py
.venv/bin/ruff check src/apps/finance tests/test_import.py
.venv/bin/black --check src/apps/finance tests/test_import.py
```

---

## 9. Fase 2 (esboço): importação de PDF

Não implementada. Resumo da abordagem prevista:

- Dependência `pdfplumber` para extração de texto.
- Parser plugável por banco (`NubankPdfParser` etc.), detectado por cabeçalho/rodapé.
- Como PDF não tem `FITID`, derivar `fitid` determinístico (hash de data + valor +
  descrição) para manter a deduplicação.
- PDF escaneado (sem camada de texto) → erro amigável, sem OCR no MVP.
- Itens com confiança baixa são sinalizados para revisão manual.

---

## 10. Como manter

- Adicionou um novo banco (OFX) com layout diferente? Ajuste apenas o parser
  (`importers.py`) e adicione fixture/teste; o restante do fluxo é reutilizado.
- Alterou a forma de casar regras? Atualize `normalize_description` e a seção 4.
- Subiu para PDF? Atualize a seção 9 e o status no cabeçalho.
