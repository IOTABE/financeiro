from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.debts.models import Debt, DebtPayment
from apps.debts.services import debt_summary, record_payment

User = get_user_model()


def make_debt(user, **kwargs) -> Debt:
    defaults = {
        "user": user,
        "creditor": "Banco X",
        "type": Debt.Type.CREDIT_CARD,
        "current_balance": Decimal("1000.00"),
        "monthly_rate": Decimal("0.0199"),
        "minimum_payment": Decimal("100.00"),
        "due_day": 10,
        "status": Debt.Status.ACTIVE,
    }
    defaults.update(kwargs)
    return Debt.objects.create(**defaults)


class DebtFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.client.force_login(self.user)

    def test_create_debt_with_monthly_rate(self):
        response = self.client.post(
            reverse("debts:create"),
            {
                "creditor": "Banco X",
                "nickname": "Cartão",
                "type": Debt.Type.CREDIT_CARD,
                "current_balance": "1000.00",
                "minimum_payment": "100.00",
                "due_day": "10",
                "status": Debt.Status.ACTIVE,
                "monthly_rate_percent": "1.99",
                "annual_rate_percent": "",
                "cet_percent": "",
                "original_amount": "1200.00",
                "installment_amount": "",
                "start_date": "",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("debts:list"))
        debt = Debt.objects.get(user=self.user)
        self.assertEqual(debt.monthly_rate, Decimal("0.0199000000"))
        self.assertEqual(debt.current_balance, Decimal("1000.00"))

    def test_create_debt_with_annual_rate_only(self):
        response = self.client.post(
            reverse("debts:create"),
            {
                "creditor": "Banco X",
                "nickname": "",
                "type": Debt.Type.PERSONAL_LOAN,
                "current_balance": "1000.00",
                "minimum_payment": "100.00",
                "due_day": "10",
                "status": Debt.Status.ACTIVE,
                "monthly_rate_percent": "",
                "annual_rate_percent": "26.82",
                "cet_percent": "",
                "original_amount": "",
                "installment_amount": "",
                "start_date": "",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("debts:list"))
        debt = Debt.objects.get(user=self.user)
        self.assertAlmostEqual(float(debt.monthly_rate), 0.019997, places=5)
        self.assertEqual(debt.annual_rate, Decimal("0.2682000000"))

    def test_paid_debt_requires_zero_balance(self):
        response = self.client.post(
            reverse("debts:create"),
            {
                "creditor": "Banco X",
                "nickname": "",
                "type": Debt.Type.OTHER,
                "current_balance": "100.00",
                "minimum_payment": "10.00",
                "due_day": "10",
                "status": Debt.Status.PAID,
                "monthly_rate_percent": "1.00",
                "annual_rate_percent": "",
                "cet_percent": "",
                "original_amount": "",
                "installment_amount": "",
                "start_date": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "saldo devedor igual a zero")

    def test_cross_user_access_returns_404(self):
        other = User.objects.create_user(email="bia@example.com", password="senha-forte-123")
        foreign = make_debt(other)
        response = self.client.get(reverse("debts:detail", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)


class DebtPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.debt = make_debt(self.user)

    def test_payment_splits_interest_and_principal(self):
        payment = record_payment(
            debt=self.debt,
            amount=Decimal("100.00"),
            paid_at=date(2026, 11, 10),
            kind=DebtPayment.Kind.MINIMUM,
        )
        self.debt.refresh_from_db()
        self.assertEqual(payment.interest_amount, Decimal("19.90"))
        self.assertEqual(payment.principal_amount, Decimal("80.10"))
        self.assertEqual(self.debt.current_balance, Decimal("919.90"))
        self.assertEqual(self.debt.status, Debt.Status.ACTIVE)

    def test_payment_below_interest_capitalizes(self):
        record_payment(debt=self.debt, amount=Decimal("10.00"), paid_at=date(2026, 11, 10))
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.current_balance, Decimal("1009.90"))

    def test_full_payment_settles_debt(self):
        record_payment(debt=self.debt, amount=Decimal("5000.00"), paid_at=date(2026, 11, 10))
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.current_balance, Decimal("0.00"))
        self.assertEqual(self.debt.status, Debt.Status.PAID)

    def test_idempotency_does_not_duplicate_payment(self):
        first = record_payment(
            debt=self.debt,
            amount=Decimal("100.00"),
            paid_at=date(2026, 11, 10),
            idempotency_key="same-key",
        )
        second = record_payment(
            debt=self.debt,
            amount=Decimal("100.00"),
            paid_at=date(2026, 11, 10),
            idempotency_key="same-key",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DebtPayment.objects.filter(debt=self.debt).count(), 1)
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.current_balance, Decimal("919.90"))

    def test_negative_amortization_detection(self):
        debt = make_debt(
            self.user,
            creditor="Cheque especial",
            monthly_rate=Decimal("0.10"),
            minimum_payment=Decimal("100.00"),
            current_balance=Decimal("1000.00"),
        )
        self.assertTrue(debt.has_negative_amortization)
        summary = debt_summary(self.user)
        self.assertIn(debt, summary["negative_amortization"])

    def test_debt_summary_totals(self):
        summary = debt_summary(self.user)
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["total_balance"], Decimal("1000.00"))
        self.assertEqual(summary["total_minimum"], Decimal("100.00"))

    def test_payment_view(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("debts:pay", args=[self.debt.pk]),
            {
                "amount": "100.00",
                "paid_at": "2026-11-10",
                "kind": DebtPayment.Kind.MINIMUM,
                "note": "",
                "idempotency_key": "view-key",
            },
        )
        self.assertRedirects(response, reverse("debts:detail", args=[self.debt.pk]))
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.current_balance, Decimal("919.90"))
