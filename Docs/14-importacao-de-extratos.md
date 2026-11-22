# 14 — Importação de Extratos Bancários (OFX e PDF)

**Objetivo:** descrever o passo a passo da importação de extratos bancários em
formato OFX e PDF, incluindo o fluxo funcional (UX), o fluxo técnico, a
categorização assistida com reaproveitamento de regras e a deduplicação.

**Status:** OFX implementado (Nubank e genérico via `ofxparse`). PDF implementado
para o layout **Santander** (texto); outros bancos exigem novo parser.
**Última atualização:** 2026-11-22

---

## 1. Visão geral

A importação transforma um extrato bancário OFX ou PDF em lançamentos
(`Transaction`) no app, sem exigir digitação manual. O fluxo tem quatro etapas:

1. **Upload** do arquivo `.ofx` ou `.pdf` e escolha da conta de destino.
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

1. Selecione o arquivo `.ofx` (ex.: `NU_75126747_01JAN2026_31JAN2026.ofx`) ou
   `.pdf` (ex.: extrato Santander).
2. Escolha a **conta** de destino (padrão: "Conta principal").
3. Clique em **"Continuar"**.

- Se o arquivo não terminar em `.ofx` nem `.pdf`, o formulário exibe
  *"Envie um arquivo no formato OFX (.ofx) ou PDF (.pdf)."*.
- Se o conteúdo for inválido, exibe uma mensagem específica: *"Não foi possível
  ler o arquivo OFX."* ou *"Não foi possível ler o arquivo PDF."*.
- PDF escaneado (sem texto selecionável) ou de layout não reconhecido gera erro
  amigável, mantendo o usuário na tela de upload.

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

### 3.1 Roteador de formato (`apps/finance/importers.py`)

`detect_format(filename, content)` decide entre OFX e PDF pela assinatura do
conteúdo (`%PDF`, `OFXHEADER:`, `<OFX>`) com fallback na extensão.
`parse_statement(filename, content)` roteia para `parse_ofx` ou `parse_pdf`.

### 3.2 Parser OFX

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

### 3.3 Parser PDF

`parse_pdf(content: bytes) -> ParsedStatement`:

1. Extrai o texto com `pdfplumber` (`_extract_pdf_text`).
2. Sem texto selecionável → erro *"O PDF não contém texto selecionável (extrato
   escaneado)..."*.
3. Itera `PDF_PARSERS` (registry) e usa o primeiro cujo `detect(text)` retorna
   `True`; hoje contém apenas `SantanderPdfParser`.
4. Layout não reconhecido → erro *"Não reconhecemos o layout deste extrato em PDF."*.

**`SantanderPdfParser`** reconhece o padrão "EXTRATO DE CONTA" + "DETALHE DOS
MOVIMENTOS" e extrai cada lançamento por linhas:

- **Linha de valor** (`DD/MM/YYYY ±R$ valor ±R$ saldo`) define data e valor;
- a **descrição** é a linha imediatamente anterior (ex.: "Pix enviado"), ou
  embutida na própria linha de valor (ex.: "Remuneracao aplicacao automatica");
- a **contraparte** é a linha seguinte, concatenada à descrição
  (`"Pix enviado - Davi Barbosa Costa Da"`); linhas `Periodo:` são ignoradas.
- `account_id` vem do cabeçalho (`Conta: 01.003475.9`).

### 3.4 Normalização e idempotência

`normalize_description(value)` normaliza a descrição para casar regras:
minúsculas, `strip`, espaços colapsados — ex.: `"  Pagamento   DE Fatura "` →
`"pagamento de fatura"`.

`idempotency_key(source, account_id, fitid)` → `f"{source}:{account_id}:{fitid}"`
(`source` é `ofx` ou `pdf`). Para OFX, `fitid` é o `FITID` do banco; para PDF,
um hash determinístico SHA-256 de `data|valor|descrição` (com sufixo `-N` para
desambiguar lançamentos idênticos dentro do mesmo arquivo).

### 3.5 Serialização na sessão

O resultado do parse é armazenado na sessão (`request.session["import_data"]`)
para sobreviver ao redirecionamento upload → preview → confirm:

```json
{
  "account_id": "<pk da Conta destino>",
  "source": "ofx",
  "source_account_id": "7512674-7",
  "transactions": [
    {"kind": "expense", "amount": "50.13", "transaction_date": "2026-01-02",
     "description": "Pagamento de fatura", "fitid": "fit-1"}
  ]
}
```

`Decimal` e `date` são serializados como string/ISO e reconstruídos nas views
via `_deserialize_import`.

### 3.6 Pré-visualização (`services.build_import_preview`)

Para cada lançamento do extrato:

1. Calcula `pattern = normalize_description(description)`.
2. Busca `CategoryRule` por `(user, kind, pattern)`; se existir, pré-seleciona a
   categoria.
3. Verifica se `idempotency_key` já existe → marca `duplicate`.

### 3.7 Aplicação (`services.apply_import`)

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
(`user`, `idempotency_key`). A chave `{source}:{account_id}:{fitid}` garante que:

- Importar o mesmo arquivo duas vezes não cria duplicatas (os itens aparecem como
  "Ignorado" na pré-visualização).
- Extratos de contas diferentes não colidem (o `account_id` entra na chave).
- OFX e PDF da mesma conta não colidem (o `source` entra na chave).

> OFX usa o `FITID` (identificador único do banco). PDF usa hash determinístico
> de `data|valor|descrição`, com contador interno para desambiguar lançamentos
> idênticos no mesmo arquivo — o que também permite deduplicar reimportações e
> extratos sobrepostos com o mesmo conteúdo.

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
- **RN-IMP-08** — PDF escaneado (sem texto) ou layout não reconhecido → erro
  amigável; não há OCR no MVP.
- **RN-IMP-09** — No PDF, `fitid` é derivado (hash) por falta de `FITID`; colisões
  dentro do mesmo arquivo são desambiguadas com sufixo sequencial.

---

## 7. Arquivos envolvidos

| Arquivo | Papel |
|---------|-------|
| `src/apps/finance/importers.py` | Roteador de formato, parser OFX, parsers PDF (registry + Santander), normalização e chave de idempotência |
| `src/apps/finance/models.py` | Modelo `CategoryRule` |
| `src/apps/finance/services.py` | `build_import_preview`, `apply_import` |
| `src/apps/finance/forms.py` | `ImportForm` (upload + conta) |
| `src/apps/finance/views.py` | `import_start`, `import_preview`, `import_confirm` |
| `src/apps/finance/urls.py` | Rotas de importação |
| `src/apps/finance/templates/finance/import_form.html` | Tela de upload |
| `src/apps/finance/templates/finance/import_preview.html` | Tela de revisão |
| `tests/test_import.py` | Testes do fluxo completo (OFX e PDF) |
| `pyproject.toml` / `requirements/base.txt` | Dependências `ofxparse` e `pdfplumber` |

---

## 8. Testes

`tests/test_import.py` cobre:

- Parser OFX: valores, datas, tipo por sinal e `account_id`.
- Normalização da descrição.
- `apply_import`: criação de transações + regra; idempotência (2ª importação = 0 criados).
- `build_import_preview`: regra existente aplicada e duplicado sinalizado.
- Fluxo de views: upload → preview → confirm; rejeição de extensão não suportada.
- Parser PDF Santander: detecção, extração (incluindo descrição embutida na linha
  de valor), `account_id`, `fitid` únicos.
- Roteamento: `detect_format`, PDF sem texto, PDF de layout desconhecido e
  integração com um arquivo PDF real (pula se ausente).

Comandos:

```bash
.venv/bin/python -m pytest tests/test_import.py
.venv/bin/ruff check src/apps/finance tests/test_import.py
.venv/bin/black --check src/apps/finance tests/test_import.py
```

---

## 9. Extensibilidade do parser PDF

Cada banco tem um `BasePdfParser` com `detect(text)` e `parse(text)`, registrado
em `PDF_PARSERS`. Para suportar um novo layout:

1. Criar a classe com `detect` (assinatura de cabeçalho) e `parse`.
2. Adicioná-la à lista `PDF_PARSERS`.
3. Adicionar fixture de texto + testes.

**Bancos já suportados:**

| Banco | Formato | Status |
|-------|---------|--------|
| Nubank (e OFX genérico) | OFX | ✅ implementado |
| Santander | PDF (texto) | ✅ implementado |
| Outros bancos (PDF) | — | ⏳ exigem novo parser |

---

## 10. Como manter

- Adicionou um novo banco (OFX ou PDF) com layout diferente? Ajuste apenas o
  parser correspondente (`importers.py`) e adicione fixture/teste; o restante do
  fluxo é reutilizado.
- Alterou a forma de casar regras? Atualize `normalize_description` e a seção 4.
- Mudou a derivação de `fitid` no PDF? Atualize a seção 5 e os testes.
