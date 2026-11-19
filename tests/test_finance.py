from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.finance.models import Account, Category, Recurrence, Transaction
from apps.finance.services import (
    create_installment_plan,
    create_recurrence,
    ensure_finance_setup,
    materialize_user_recurrences,
)

User = get_user_model()


class FinanceSetupTests(TestCase):
    def test_new_user_gets_categories_and_main_account(self):
        user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.assertTrue(Category.objects.filter(user=user).exists())
        self.assertTrue(Account.objects.filter(user=user, name="Conta principal").exists())

    def test_ensure_setup_is_idempotent(self):
        user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        initial_categories = Category.objects.filter(user=user).count()
        initial_accounts = Account.objects.filter(user=user).count()
        ensure_finance_setup(user)
        self.assertEqual(Category.objects.filter(user=user).count(), initial_categories)
        self.assertEqual(Account.objects.filter(user=user).count(), initial_accounts)


class TransactionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.other = User.objects.create_user(email="bia@example.com", password="senha-forte-123")
        self.client.force_login(self.user)
        self.category = Category.objects.filter(user=self.user, kind=Category.Kind.EXPENSE).first()
        self.account = Account.objects.filter(user=self.user).first()

    def test_create_transaction(self):
        response = self.client.post(
            reverse("finance:transaction_create"),
            {
                "kind": Transaction.Kind.EXPENSE,
                "amount": "150.00",
                "description": "Supermercado",
                "transaction_date": "2026-11-10",
                "category": str(self.category.pk),
                "account": str(self.account.pk),
                "status": Transaction.Status.PAID,
            },
        )
        self.assertRedirects(response, reverse("finance:transactions"))
        transaction = Transaction.objects.get(user=self.user)
        self.assertEqual(transaction.amount, Decimal("150.00"))
        self.assertEqual(transaction.competence_month, date(2026, 11, 1))
        self.assertEqual(transaction.paid_at, date(2026, 11, 10))

    def test_list_filters_and_isolates_users(self):
        Transaction.objects.create(
            user=self.user,
            kind=Transaction.Kind.EXPENSE,
            amount="100.00",
            description="Mercado",
            transaction_date=date(2026, 11, 5),
            competence_month=date(2026, 11, 1),
            status=Transaction.Status.PAID,
            paid_at=date(2026, 11, 5),
        )
        Transaction.objects.create(
            user=self.other,
            kind=Transaction.Kind.EXPENSE,
            amount="999.00",
            description="Outro usuário",
            transaction_date=date(2026, 11, 6),
            competence_month=date(2026, 11, 1),
            status=Transaction.Status.PAID,
            paid_at=date(2026, 11, 6),
        )
        response = self.client.get(
            reverse("finance:transactions"),
            {"from": "2026-11-01", "to": "2026-11-30", "kind": "expense"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [t.pk for t in response.context["page"].object_list]
        self.assertEqual(len(ids), 1)
        self.assertNotIn("Outro usuário", response.content.decode())

    def test_cross_user_edit_returns_404(self):
        foreign = Transaction.objects.create(
            user=self.other,
            kind=Transaction.Kind.EXPENSE,
            amount="100.00",
            description="Privado",
            transaction_date=date(2026, 11, 5),
            competence_month=date(2026, 11, 1),
            status=Transaction.Status.PAID,
            paid_at=date(2026, 11, 5),
        )
        response = self.client.get(reverse("finance:transaction_update", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_paid(self):
        transaction = Transaction.objects.create(
            user=self.user,
            kind=Transaction.Kind.EXPENSE,
            amount="100.00",
            description="Pendente",
            transaction_date=date(2026, 11, 5),
            competence_month=date(2026, 11, 1),
            status=Transaction.Status.PENDING,
        )
        response = self.client.post(reverse("finance:transaction_toggle", args=[transaction.pk]))
        self.assertRedirects(response, reverse("finance:transactions"))
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, Transaction.Status.PAID)
        self.assertEqual(transaction.paid_at, transaction.transaction_date)

    def test_create_installment_plan(self):
        group = create_installment_plan(
            user=self.user,
            description="Notebook",
            total_amount=Decimal("100.00"),
            installments=3,
            first_due_date=date(2026, 12, 5),
            category=self.category,
            account=self.account,
        )
        transactions = group.transactions.order_by("installment_number")
        self.assertEqual(transactions.count(), 3)
        self.assertEqual(sum(t.amount for t in transactions), Decimal("100.00"))
        self.assertEqual(
            [t.amount for t in transactions], [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
        )
        self.assertTrue(all(t.status == Transaction.Status.PENDING for t in transactions))

    def test_create_recurrence_materializes_and_is_idempotent(self):
        recurrence = create_recurrence(
            user=self.user,
            description="Aluguel",
            kind=Recurrence.Kind.EXPENSE,
            amount=Decimal("1800.00"),
            due_day=5,
            start_date=date(2026, 1, 1),
            category=self.category,
            account=self.account,
        )
        materialize_user_recurrences(self.user, date(2026, 3, 31))
        materialize_user_recurrences(self.user, date(2026, 3, 31))
        transactions = Transaction.objects.filter(user=self.user, recurrence=recurrence)
        self.assertEqual(transactions.count(), 3)
        self.assertEqual(
            set(transactions.values_list("competence_month", flat=True)),
            {date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)},
        )
        recurrence.refresh_from_db()
        self.assertEqual(recurrence.next_run, date(2026, 4, 5))


class CategoryAndAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.client.force_login(self.user)

    def test_duplicate_category_is_rejected(self):
        response = self.client.post(
            reverse("finance:category_create"),
            {"name": "Lazer", "kind": Category.Kind.EXPENSE, "is_essential": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe uma categoria")

    def test_category_archive(self):
        category = Category.objects.filter(user=self.user, kind=Category.Kind.EXPENSE).first()
        response = self.client.post(reverse("finance:category_archive", args=[category.pk]))
        self.assertRedirects(response, reverse("finance:categories"))
        category.refresh_from_db()
        self.assertIsNotNone(category.archived_at)

    def test_create_account(self):
        response = self.client.post(
            reverse("finance:account_create"),
            {"name": "Poupança", "type": Account.Type.SAVINGS, "opening_balance": "1000.00"},
        )
        self.assertRedirects(response, reverse("finance:accounts"))
        self.assertTrue(Account.objects.filter(user=self.user, name="Poupança").exists())

    def test_cross_user_category_access_returns_404(self):
        other = User.objects.create_user(email="bia@example.com", password="senha-forte-123")
        foreign = Category.objects.filter(user=other).first()
        response = self.client.get(reverse("finance:category_update", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)
