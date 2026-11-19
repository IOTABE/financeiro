from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.debts.models import Debt
from apps.plans.models import Plan, PlanPayment, Simulation
from apps.plans.services import (
    adherence_summary,
    apply_simulation,
    compare_for_user,
    current_plan,
    generate_plan,
    mark_schedule_paid,
    simulate_scenario,
)

User = get_user_model()


def setup_user(email="ana@example.com"):
    user = User.objects.create_user(email=email, password="senha-forte-123")
    profile = user.profile
    profile.net_income = Decimal("4200.00")
    profile.gross_income = Decimal("5200.00")
    profile.essential_expenses = Decimal("2600.00")
    profile.min_existential = Decimal("1800.00")
    profile.other_planned_expenses = Decimal("200.00")
    profile.save()
    return user


def make_debt(user, creditor="Banco X", balance="6000.00", rate="0.0199", minimum="300.00", due=10):
    return Debt.objects.create(
        user=user,
        creditor=creditor,
        nickname=creditor,
        type=Debt.Type.CREDIT_CARD,
        current_balance=Decimal(balance),
        monthly_rate=Decimal(rate),
        minimum_payment=Decimal(minimum),
        due_day=due,
        status=Debt.Status.ACTIVE,
    )


def make_three_debts(user):
    return (
        make_debt(user, "Cartão", "6000.00", "0.0199", "300.00"),
        make_debt(user, "Empréstimo", "4000.00", "0.0125", "250.00"),
        make_debt(user, "Parcelado", "2000.00", "0.0099", "200.00"),
    )


class PlanGenerationTests(TestCase):
    def setUp(self):
        self.user = setup_user()
        make_three_debts(self.user)

    def test_generate_plan_persists_items_and_schedule(self):
        plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        self.assertEqual(plan.status, Plan.Status.ACTIVE)
        self.assertEqual(plan.engine_version, "1")
        self.assertEqual(plan.monthly_available, Decimal("1400.00"))
        self.assertGreater(plan.months_to_payoff, 0)
        self.assertEqual(plan.items.count(), 3)
        self.assertGreater(plan.schedule.count(), 0)
        for row in plan.schedule.all():
            self.assertEqual(
                row.payment + row.capitalized_interest,
                row.interest + row.principal,
                f"reconciliação falhou em {row.competence_month}",
            )
        self.assertEqual(plan.input_snapshot["debts"][0]["id"], str(plan.items.first().debt_id))
        self.assertEqual(current_plan(self.user), plan)

    def test_generate_twice_archives_previous(self):
        first = generate_plan(self.user, strategy="avalanche", start_month=date(2026, 1, 1))
        second = generate_plan(self.user, strategy="snowball", start_month=date(2026, 1, 1))
        first.refresh_from_db()
        self.assertEqual(first.status, Plan.Status.ARCHIVED)
        self.assertEqual(second.status, Plan.Status.ACTIVE)
        self.assertEqual(Plan.objects.filter(user=self.user, status=Plan.Status.ACTIVE).count(), 1)

    def test_infeasible_plan_has_no_schedule(self):
        profile = self.user.profile
        profile.net_income = Decimal("1000.00")
        profile.essential_expenses = Decimal("900.00")
        profile.other_planned_expenses = Decimal("0")
        profile.save()
        for debt in Debt.objects.filter(user=self.user):
            debt.minimum_payment = Decimal("500.00")
            debt.save()
        plan = generate_plan(self.user, strategy="avalanche", start_month=date(2026, 1, 1))
        self.assertEqual(plan.status, Plan.Status.INFEASIBLE)
        self.assertTrue(plan.infeasible_reason)
        self.assertEqual(plan.items.count(), 0)
        self.assertEqual(plan.schedule.count(), 0)

    def test_debt_change_marks_plan_stale(self):
        plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        debt = Debt.objects.filter(user=self.user).first()
        debt.current_balance = Decimal("5000.00")
        debt.save()
        plan.refresh_from_db()
        self.assertEqual(plan.status, Plan.Status.STALE)

    def test_profile_change_marks_plan_stale(self):
        plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        profile = self.user.profile
        profile.net_income = Decimal("5000.00")
        profile.save()
        plan.refresh_from_db()
        self.assertEqual(plan.status, Plan.Status.STALE)

    def test_compare_for_user(self):
        comparison = compare_for_user(self.user, start_month=date(2026, 1, 1))
        self.assertEqual(set(comparison["strategies"]), {"avalanche", "snowball", "hybrid"})
        self.assertIn(comparison["recommendation"], {"avalanche", "hybrid"})
        self.assertEqual(comparison["monthly_available"], "1400.00")

    def test_simulate_expense_cut_and_apply(self):
        plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        simulation = simulate_scenario(
            self.user,
            kind=Simulation.Kind.EXPENSE_CUT,
            params={"expense_cut": Decimal("300.00")},
            name="Cortar lazer",
            base_plan=plan,
        )
        self.assertEqual(simulation.kind, Simulation.Kind.EXPENSE_CUT)
        self.assertIn("baseline", simulation.result_summary)
        self.assertLessEqual(
            simulation.result_summary["scenario"]["months"],
            simulation.result_summary["baseline"]["months"],
        )
        new_plan = apply_simulation(simulation)
        self.assertEqual(new_plan.status, Plan.Status.ACTIVE)
        self.assertEqual(new_plan.label, "Cortar lazer")
        simulation.refresh_from_db()
        self.assertIsNotNone(simulation.applied_at)
        self.assertEqual(current_plan(self.user), new_plan)


class PlanViewTests(TestCase):
    def setUp(self):
        self.user = setup_user()
        make_three_debts(self.user)
        self.client.force_login(self.user)

    def test_current_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("plans:current"))
        self.assertEqual(response.status_code, 302)

    def test_current_page_shows_start_form_without_plan(self):
        response = self.client.get(reverse("plans:current"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerar plano")

    def test_generate_and_detail(self):
        response = self.client.post(
            reverse("plans:generate"),
            {
                "strategy": "hybrid",
                "start_month": "2026-01-01",
                "extra_payment": "0",
                "extra_payment_months": "0",
            },
        )
        plan = Plan.objects.get(user=self.user)
        self.assertRedirects(response, reverse("plans:detail", args=[plan.pk]))
        detail = self.client.get(reverse("plans:detail", args=[plan.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Ordem de pagamento")
        self.assertContains(detail, "Calendário")

    def test_compare_page(self):
        response = self.client.get(reverse("plans:compare"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avalanche")
        self.assertContains(response, "Híbrida")

    def test_simulator_and_apply(self):
        generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        page = self.client.get(reverse("plans:simulator"))
        self.assertEqual(page.status_code, 200)
        response = self.client.post(
            reverse("plans:simulator"),
            {
                "kind": Simulation.Kind.EXPENSE_CUT,
                "name": "Cortar lazer",
                "expense_cut": "300.00",
                "extra_income": "",
                "extra_income_months": "0",
                "debt_id": "",
                "new_rate_percent": "",
                "new_term_months": "",
                "discount_percent": "",
                "entry_payment": "",
                "income_factor": "0.800",
                "expense_factor": "1.100",
            },
        )
        simulation = Simulation.objects.get(user=self.user)
        self.assertRedirects(response, reverse("plans:simulation_detail", args=[simulation.pk]))
        detail = self.client.get(reverse("plans:simulation_detail", args=[simulation.pk]))
        self.assertEqual(detail.status_code, 200)
        apply_response = self.client.post(reverse("plans:apply_simulation", args=[simulation.pk]))
        plan = current_plan(self.user)
        self.assertRedirects(apply_response, reverse("plans:detail", args=[plan.pk]))

    def test_cross_user_plan_returns_404(self):
        other = setup_user("bia@example.com")
        foreign = generate_plan(other, strategy="hybrid", start_month=date(2026, 1, 1))
        response = self.client.get(reverse("plans:detail", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_recalculate(self):
        plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))
        debt = Debt.objects.filter(user=self.user).first()
        debt.current_balance = Decimal("5500.00")
        debt.save()
        plan.refresh_from_db()
        self.assertEqual(plan.status, Plan.Status.STALE)
        response = self.client.post(reverse("plans:recalculate", args=[plan.pk]))
        new_plan = Plan.objects.filter(user=self.user, status=Plan.Status.ACTIVE).first()
        self.assertRedirects(response, reverse("plans:detail", args=[new_plan.pk]))
        self.assertNotEqual(plan.pk, new_plan.pk)


class PlanAdherenceTests(TestCase):
    def setUp(self):
        self.user = setup_user()
        make_three_debts(self.user)
        self.plan = generate_plan(self.user, strategy="hybrid", start_month=date(2026, 1, 1))

    def test_mark_schedule_paid_and_summary(self):
        schedule = self.plan.schedule.filter(payment__gt=0).first()
        payment = mark_schedule_paid(user=self.user, schedule=schedule, paid_at=date(2026, 1, 10))
        self.assertEqual(payment.amount, schedule.payment)
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_paid)
        summary = adherence_summary(self.plan, today=date(2026, 1, 31))
        self.assertEqual(summary["due"], 3)
        self.assertEqual(summary["paid"], 1)
        self.assertEqual(summary["pending"], 2)

    def test_mark_schedule_paid_is_idempotent(self):
        schedule = self.plan.schedule.filter(payment__gt=0).first()
        first = mark_schedule_paid(user=self.user, schedule=schedule)
        second = mark_schedule_paid(user=self.user, schedule=schedule)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PlanPayment.objects.filter(plan=self.plan).count(), 1)

    def test_schedule_pay_view_and_isolation(self):
        self.client.force_login(self.user)
        schedule = self.plan.schedule.filter(payment__gt=0).first()
        response = self.client.post(reverse("plans:schedule_pay", args=[schedule.pk]))
        self.assertRedirects(response, reverse("plans:detail", args=[self.plan.pk]))
        self.assertTrue(PlanPayment.objects.filter(schedule=schedule).exists())

        other = setup_user("bia@example.com")
        make_debt(other)
        foreign_plan = generate_plan(other, strategy="hybrid", start_month=date(2026, 1, 1))
        foreign_schedule = foreign_plan.schedule.filter(payment__gt=0).first()
        response = self.client.post(reverse("plans:schedule_pay", args=[foreign_schedule.pk]))
        self.assertEqual(response.status_code, 404)
