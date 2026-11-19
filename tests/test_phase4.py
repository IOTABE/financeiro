from __future__ import annotations

import json
from datetime import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.debts.models import Debt
from apps.finance.models import Transaction
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import send_due_reminders_for_user
from apps.plans.models import Plan, PlanPayment

User = get_user_model()


def make_user(email="ana@example.com", password="senha-forte-123"):
    user = User.objects.create_user(email=email, password=password)
    profile = user.profile
    profile.net_income = Decimal("4200.00")
    profile.gross_income = Decimal("5200.00")
    profile.essential_expenses = Decimal("2600.00")
    profile.min_existential = Decimal("1800.00")
    profile.other_planned_expenses = Decimal("200.00")
    profile.onboarding_completed_at = timezone.now()
    profile.save()
    return user


def make_debt(user, due_day=10):
    return Debt.objects.create(
        user=user,
        creditor="Banco X",
        nickname="Cartão",
        type=Debt.Type.CREDIT_CARD,
        current_balance=Decimal("6000.00"),
        monthly_rate=Decimal("0.0199"),
        minimum_payment=Decimal("300.00"),
        due_day=due_day,
        status=Debt.Status.ACTIVE,
    )


class ReportAndExportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()
        make_debt(self.user)
        Transaction.objects.create(
            user=self.user,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("100.00"),
            description="Mercado",
            transaction_date=timezone.localdate(),
            competence_month=timezone.localdate().replace(day=1),
            status=Transaction.Status.PAID,
            paid_at=timezone.localdate(),
        )
        self.client.force_login(self.user)

    def test_monthly_report(self):
        response = self.client.get(reverse("reports:monthly"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resumo de")
        self.assertContains(response, "Mercado")

    def test_export_json_and_audit(self):
        response = self.client.get(reverse("reports:export_json"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        payload = json.loads(response.content)
        self.assertEqual(payload["user"]["email"], self.user.email)
        self.assertTrue(AuditLog.objects.filter(user=self.user, event="data.exported").exists())

    def test_export_csv(self):
        response = self.client.get(reverse("reports:export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("Mercado", response.content.decode())


class NotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()
        self.debt = make_debt(self.user, due_day=timezone.localdate().day)
        preferences = NotificationPreference.objects.create(user=self.user)
        preferences.quiet_hours_start = time(0, 0)
        preferences.quiet_hours_end = time(0, 0)
        preferences.save()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_due_reminder_is_created_and_sent_once(self):
        first = send_due_reminders_for_user(self.user)
        second = send_due_reminders_for_user(self.user)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Pagamento próximo", mail.outbox[0].subject)

    def test_preferences_and_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:preferences"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("notifications:preferences"),
            {
                "email_enabled": "on",
                "due_reminders": "on",
                "risk_alerts": "on",
                "weekly_summary": "",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
            },
        )
        self.assertRedirects(response, reverse("notifications:preferences"))
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(prefs.weekly_summary)

        notification = Notification.objects.create(
            user=self.user,
            kind=Notification.Kind.SYSTEM,
            title="Teste",
            body="Mensagem",
        )
        listing = self.client.get(reverse("notifications:list"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "Teste")
        read = self.client.post(reverse("notifications:mark_read", args=[notification.pk]))
        self.assertRedirects(read, reverse("notifications:list"))
        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.Status.READ)


class AccountDeletionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()
        make_debt(self.user)
        self.client.force_login(self.user)

    def test_my_data_page(self):
        response = self.client.get(reverse("accounts:my_data"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exportar")

    def test_delete_requires_password(self):
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"password": "errada", "confirmation": "EXCLUIR"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account_keeps_audit_without_identity(self):
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"password": "senha-forte-123", "confirmation": "EXCLUIR"},
        )
        self.assertRedirects(response, "/?deleted=1")
        self.assertFalse(User.objects.filter(email=self.user.email).exists())
        entry = AuditLog.objects.get(event="account.deleted")
        self.assertIsNone(entry.user)


class SecurityHeaderTests(TestCase):
    def test_security_headers_are_present(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("default-src", response["Content-Security-Policy"])
        self.assertEqual(response["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()

    def test_login_is_rate_limited(self):
        url = reverse("accounts:login")
        for _ in range(5):
            response = self.client.post(url, {"username": self.user.email, "password": "errada"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {"username": self.user.email, "password": "errada"})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Muitas tentativas", status_code=429)


class SeedDemoTests(TestCase):
    def test_seed_demo_creates_plan(self):
        call_command("seed_demo", email="demo-test@example.com", password="DemoClareza123")
        user = User.objects.get(email="demo-test@example.com")
        self.assertTrue(user.profile.has_income)
        self.assertTrue(Debt.objects.filter(user=user).exists())
        self.assertTrue(Plan.objects.filter(user=user, status=Plan.Status.ACTIVE).exists())


class FullFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_full_flow_from_registration_to_plan_adherence(self):
        register = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Ana Fluxo",
                "email": "fluxo@example.com",
                "password1": "UmaSenhaMuitoForte123",
                "password2": "UmaSenhaMuitoForte123",
                "accept_terms": "on",
                "accept_privacy": "on",
            },
        )
        self.assertRedirects(register, reverse("core:dashboard"))
        user = User.objects.get(email="fluxo@example.com")

        profile = self.client.post(
            reverse("accounts:profile"),
            {
                "gross_income": "5200.00",
                "net_income": "4200.00",
                "essential_expenses": "2600.00",
                "min_existential": "1800.00",
                "other_planned_expenses": "200.00",
                "income_type": "fixed",
                "conservative_factor": "0.800",
                "dependents": "1",
                "theme": "system",
                "complete_onboarding": "1",
            },
        )
        self.assertRedirects(profile, reverse("core:dashboard"))

        debt = self.client.post(
            reverse("debts:create"),
            {
                "creditor": "Cartão",
                "nickname": "Cartão",
                "type": Debt.Type.CREDIT_CARD,
                "current_balance": "6000.00",
                "minimum_payment": "300.00",
                "due_day": "10",
                "status": Debt.Status.ACTIVE,
                "monthly_rate_percent": "1.99",
                "annual_rate_percent": "",
                "cet_percent": "",
                "original_amount": "6000.00",
                "installment_amount": "",
                "start_date": "",
                "notes": "",
            },
        )
        self.assertRedirects(debt, reverse("debts:list"))

        generated = self.client.post(
            reverse("plans:generate"),
            {
                "strategy": "hybrid",
                "start_month": "2026-01-01",
                "extra_payment": "0",
                "extra_payment_months": "0",
            },
        )
        plan = Plan.objects.get(user=user, status=Plan.Status.ACTIVE)
        self.assertRedirects(generated, reverse("plans:detail", args=[plan.pk]))

        schedule = plan.schedule.filter(payment__gt=0).first()
        paid = self.client.post(reverse("plans:schedule_pay", args=[schedule.pk]))
        self.assertRedirects(paid, reverse("plans:detail", args=[plan.pk]))
        self.assertTrue(PlanPayment.objects.filter(plan=plan).exists())

        report = self.client.get(reverse("reports:monthly"))
        self.assertEqual(report.status_code, 200)

        export = self.client.get(reverse("reports:export_json"))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(json.loads(export.content)["user"]["email"], user.email)
