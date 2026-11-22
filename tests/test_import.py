from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.finance.importers import normalize_description, parse_ofx
from apps.finance.models import Account, Category, CategoryRule, Transaction
from apps.finance.services import apply_import, build_import_preview

User = get_user_model()

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
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        created, skipped = apply_import(
            user=self.user,
            account=self.account,
            source_account_id="7512674-7",
            rows=self._rows(category_id=str(self.category.pk)),
        )
        self.assertEqual((created, skipped), (0, 2))
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)

    def test_build_preview_applies_existing_rule(self):
        apply_import(
            user=self.user,
            account=self.account,
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

    def test_rejects_non_ofx(self):
        response = self.client.post(
            reverse("finance:import_start"),
            {
                "account": str(self.account.pk),
                "file": SimpleUploadedFile("extrato.pdf", b"%PDF-1.4 fake"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "formato OFX")
