from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.finance.importers import (
    ImportError as ImportParseError,
)
from apps.finance.importers import (
    SantanderPdfParser,
    detect_format,
    normalize_description,
    parse_ofx,
    parse_pdf,
)
from apps.finance.models import Account, Category, CategoryRule, Transaction
from apps.finance.services import apply_import, build_import_preview

User = get_user_model()

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_SAMPLE_PATH = (
    BASE_DIR / "extrato_25-08-2026_a_22-11-2026_660561DE-E868-4CC6-B708-652655CE5878.pdf"
)

OFX_SAMPLE = """<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL</CURDEF>
<BANKACCTFROM><BANKID>0260</BANKID><ACCTID>7512674-7</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260102000000[-3:BRT]</DTPOSTED><TRNAMT>-50.13</TRNAMT><FITID>fit-1</FITID><MEMO>Pagamento de fatura</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260105000000[-3:BRT]</DTPOSTED><TRNAMT>397.00</TRNAMT><FITID>fit-2</FITID><MEMO>Transferência recebida pelo Pix</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


class OfxParserTests(TestCase):
    def test_parse_ofx_basic(self):
        parsed = parse_ofx(OFX_SAMPLE.encode())
        self.assertEqual(parsed.account_id, "7512674-7")
        self.assertEqual(len(parsed.transactions), 2)

        debit, credit = parsed.transactions
        self.assertEqual(debit.kind, Transaction.Kind.EXPENSE)
        self.assertEqual(debit.amount, Decimal("50.13"))
        self.assertEqual(debit.transaction_date, date(2026, 1, 2))
        self.assertEqual(debit.description, "Pagamento de fatura")
        self.assertEqual(debit.fitid, "fit-1")

        self.assertEqual(credit.kind, Transaction.Kind.INCOME)
        self.assertEqual(credit.amount, Decimal("397.00"))
        self.assertEqual(credit.transaction_date, date(2026, 1, 5))

    def test_normalize_description(self):
        self.assertEqual(normalize_description("  Pagamento   DE Fatura "), "pagamento de fatura")
        self.assertEqual(normalize_description(None), "")


class ImportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.account = Account.objects.filter(user=self.user).first()
        self.category = Category.objects.filter(
            user=self.user, kind=Category.Kind.EXPENSE, name="Assinaturas"
        ).first()

    def _rows(self, category_id=None):
        return [
            {
                "fitid": "fit-1",
                "kind": Transaction.Kind.EXPENSE,
                "amount": Decimal("50.13"),
                "transaction_date": date(2026, 1, 2),
                "description": "Pagamento de fatura",
                "category_id": category_id,
            },
            {
                "fitid": "fit-2",
                "kind": Transaction.Kind.INCOME,
                "amount": Decimal("397.00"),
                "transaction_date": date(2026, 1, 5),
                "description": "Transferência recebida pelo Pix",
                "category_id": None,
            },
        ]

    def test_apply_import_creates_transactions_and_rule(self):
        created, skipped = apply_import(
            user=self.user,
            account=self.account,
            source="ofx",
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        self.assertEqual((created, skipped), (2, 0))

        transaction = Transaction.objects.get(user=self.user, idempotency_key="ofx:7512674-7:fit-1")
        self.assertEqual(transaction.status, Transaction.Status.PAID)
        self.assertEqual(transaction.paid_at, date(2026, 1, 2))
        self.assertEqual(transaction.category, self.category)

        rule = CategoryRule.objects.get(
            user=self.user, kind=Transaction.Kind.EXPENSE, pattern="pagamento de fatura"
        )
        self.assertEqual(rule.category, self.category)

    def test_apply_import_is_idempotent(self):
        apply_import(
            user=self.user,
            account=self.account,
            source="ofx",
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        created, skipped = apply_import(
            user=self.user,
            account=self.account,
            source="ofx",
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        self.assertEqual((created, skipped), (0, 2))
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)

    def test_build_preview_applies_existing_rule(self):
        apply_import(
            user=self.user,
            account=self.account,
            source="ofx",
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        parsed = parse_ofx(OFX_SAMPLE.encode())
        preview = build_import_preview(self.user, parsed)
        debit = next(item for item in preview if item["fitid"] == "fit-1")
        credit = next(item for item in preview if item["fitid"] == "fit-2")
        self.assertEqual(debit["category_id"], str(self.category.pk))
        self.assertTrue(debit["duplicate"])
        self.assertIsNone(credit["category_id"])


class ImportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.client.force_login(self.user)
        self.account = Account.objects.filter(user=self.user).first()
        self.category = Category.objects.filter(
            user=self.user, kind=Category.Kind.EXPENSE, name="Assinaturas"
        ).first()

    def test_full_import_flow(self):
        upload = self.client.post(
            reverse("finance:import_start"),
            {
                "account": str(self.account.pk),
                "file": SimpleUploadedFile("extrato.ofx", OFX_SAMPLE.encode()),
            },
        )
        self.assertRedirects(upload, reverse("finance:import_preview"))

        preview = self.client.get(reverse("finance:import_preview"))
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Pagamento de fatura")

        confirm = self.client.post(
            reverse("finance:import_confirm"),
            {f"category_{0}": str(self.category.pk), "category_1": ""},
        )
        self.assertRedirects(confirm, reverse("finance:transactions"))
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)
        self.assertTrue(
            CategoryRule.objects.filter(
                user=self.user, pattern="pagamento de fatura", category=self.category
            ).exists()
        )

    def test_rejects_unsupported_extension(self):
        response = self.client.post(
            reverse("finance:import_start"),
            {
                "account": str(self.account.pk),
                "file": SimpleUploadedFile("extrato.txt", b"qualquer coisa"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "formato OFX")


SANTANDER_TEXT = """EXTRATO DE CONTA
Agência: 2302 | Conta: 01.003475.9
Período: 25/08/2026 a 22/11/2026
Nome: Joao
Saldo inicial Entradas Saídas Saldo final
-R$ 2.470,38 R$ 17.155,33 R$ 17.621,84 -R$ 2.936,89
DETALHE DOS MOVIMENTOS
Data Descrição Valor Saldo
Quarta, 18 de novembro
Pix enviado
18/11/2026 -R$ 15,00 -R$ 2.936,89
Davi Barbosa Costa Da
Segunda, 16 de novembro
Debito aut. titulo capitalizacao
16/11/2026 -R$ 50,00 -R$ 2.921,89
Icj60212075
Ted conta salario
16/11/2026 R$ 5.638,41 R$ 2.365,14
Joao barbosa da silva
1/1"""


def _minimal_pdf(stream: bytes = b"") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for index in range(1, len(objects) + 1):
        out += f"{offsets[index]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


class SantanderPdfParserTests(TestCase):
    def setUp(self):
        self.parser = SantanderPdfParser()

    def test_detect(self):
        self.assertTrue(self.parser.detect(SANTANDER_TEXT))
        self.assertFalse(self.parser.detect("EXTRATO DE CONTA\nSem detalhe dos movimentos"))

    def test_parse_extracts_transactions(self):
        statement = self.parser.parse(SANTANDER_TEXT)
        self.assertEqual(statement.source, "pdf")
        self.assertEqual(statement.account_id, "01.003475.9")
        self.assertEqual(len(statement.transactions), 3)

        debit, debit2, credit = statement.transactions
        self.assertEqual(debit.kind, Transaction.Kind.EXPENSE)
        self.assertEqual(debit.amount, Decimal("15.00"))
        self.assertEqual(debit.transaction_date, date(2026, 11, 18))
        self.assertEqual(debit.description, "Pix enviado - Davi Barbosa Costa Da")

        self.assertEqual(debit2.description, "Debito aut. titulo capitalizacao - Icj60212075")

        self.assertEqual(credit.kind, Transaction.Kind.INCOME)
        self.assertEqual(credit.amount, Decimal("5638.41"))
        self.assertEqual(credit.description, "Ted conta salario - Joao barbosa da silva")

    def test_parse_generates_unique_fitids(self):
        statement = self.parser.parse(SANTANDER_TEXT)
        fitids = [item.fitid for item in statement.transactions]
        self.assertEqual(len(fitids), len(set(fitids)))

    def test_parse_inline_description(self):
        text = (
            "EXTRATO DE CONTA\n"
            "Agência: 2302 | Conta: 01.003475.9\n"
            "DETALHE DOS MOVIMENTOS\n"
            "Data Descrição Valor Saldo\n"
            "Quarta, 11 de novembro\n"
            "11/11/2026 Remuneracao aplicacao automatica R$ 0,01 -R$ 2.564,84\n"
            "Pagamento cartao credito bce\n"
            "11/11/2026 -R$ 1.635,08 -R$ 2.564,85\n"
            "Banco Santander (br)\n"
        )
        statement = self.parser.parse(text)
        self.assertEqual(len(statement.transactions), 2)

        remuneracao = statement.transactions[0]
        self.assertEqual(remuneracao.kind, Transaction.Kind.INCOME)
        self.assertEqual(remuneracao.amount, Decimal("0.01"))
        self.assertEqual(remuneracao.description, "Remuneracao aplicacao automatica")

        fatura = statement.transactions[1]
        self.assertEqual(fatura.kind, Transaction.Kind.EXPENSE)
        self.assertEqual(fatura.amount, Decimal("1635.08"))
        self.assertEqual(fatura.description, "Pagamento cartao credito bce - Banco Santander (br)")


class PdfRoutingTests(TestCase):
    def test_detect_format(self):
        self.assertEqual(detect_format("x.pdf", b"%PDF-1.4"), "pdf")
        self.assertEqual(detect_format("x.ofx", b"<OFX>"), "ofx")
        with self.assertRaises(ImportParseError):
            detect_format("x.txt", b"whatever")

    def test_parse_pdf_no_text(self):
        with self.assertRaises(ImportParseError):
            parse_pdf(_minimal_pdf())

    def test_parse_pdf_unknown_layout(self):
        stream = b"BT /F1 12 Tf 50 700 Td (HELLO) Tj ET"
        with self.assertRaises(ImportParseError):
            parse_pdf(_minimal_pdf(stream))

    def test_parse_pdf_real_file(self):
        if not PDF_SAMPLE_PATH.exists():
            self.skipTest("Arquivo de exemplo PDF não disponível")
        parsed = parse_pdf(PDF_SAMPLE_PATH.read_bytes())
        self.assertEqual(parsed.source, "pdf")
        self.assertGreater(len(parsed.transactions), 10)
        for item in parsed.transactions:
            self.assertIn(item.kind, {Transaction.Kind.INCOME, Transaction.Kind.EXPENSE})
            self.assertTrue(item.amount > 0)
