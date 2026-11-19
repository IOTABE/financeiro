from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.plans.engine import (
    DebtInput,
    PlanInput,
    annual_rate_from_monthly,
    compare_strategies,
    implied_rate,
    monthly_rate_from_annual,
    pmt,
    simulate,
)

START = date(2026, 1, 1)


def debt(identifier, balance, rate, minimum, due_day=10, locked=None):
    return DebtInput(
        id=identifier,
        name=identifier,
        balance=Decimal(str(balance)),
        monthly_rate=Decimal(str(rate)),
        minimum_payment=Decimal(str(minimum)),
        due_day=due_day,
        priority_locked=locked,
    )


class RateTests(SimpleTestCase):
    def test_monthly_from_annual(self):
        monthly = monthly_rate_from_annual(Decimal("0.12"))
        self.assertAlmostEqual(float(monthly), 0.0094887929, places=9)

    def test_round_trip(self):
        annual = annual_rate_from_monthly(Decimal("0.0199"))
        self.assertAlmostEqual(float(monthly_rate_from_annual(annual)), 0.0199, places=9)

    def test_pmt_and_implied_rate(self):
        payment = pmt(Decimal("1000"), Decimal("0.01"), 12)
        rate = implied_rate(Decimal("1000"), payment, 12)
        self.assertAlmostEqual(float(rate), 0.01, places=6)

    def test_pmt_zero_rate(self):
        self.assertEqual(pmt(Decimal("1200"), Decimal("0"), 12), Decimal("100"))


class GoldenCaseTests(SimpleTestCase):
    def test_single_debt(self):
        result = simulate(
            PlanInput(
                monthly_available=Decimal("300"),
                debts=(debt("D", "1000", "0.02", "100"),),
                strategy="avalanche",
                start_month=START,
            )
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.months, 4)
        self.assertEqual(result.total_interest, Decimal("45.95"))
        self.assertEqual(result.total_paid, Decimal("1045.95"))
        self.assertEqual(result.debt_free_date, date(2026, 5, 1))

    def test_three_debts_avalanche_and_snowball(self):
        debts = (
            debt("Cartao", "6000", "0.0199", "300"),
            debt("Emprestimo", "4000", "0.0125", "250"),
            debt("Parcelado", "2000", "0.0099", "200"),
        )
        avalanche = simulate(PlanInput(Decimal("1200"), debts, "avalanche", start_month=START))
        snowball = simulate(PlanInput(Decimal("1200"), debts, "snowball", start_month=START))
        self.assertEqual(avalanche.status, "ok")
        self.assertEqual(avalanche.months, 11)
        self.assertEqual(avalanche.total_interest, Decimal("1112.02"))
        self.assertEqual(avalanche.first_payoff.debt_id, "Cartao")
        self.assertEqual(avalanche.first_payoff.month_index, 9)

        self.assertEqual(snowball.status, "ok")
        self.assertEqual(snowball.months, 12)
        self.assertEqual(snowball.total_interest, Decimal("1287.88"))
        self.assertEqual(snowball.first_payoff.debt_id, "Parcelado")
        self.assertEqual(snowball.first_payoff.month_index, 4)

    def test_four_debts_hybrid_quick_win(self):
        debts = (
            debt("Cartao", "6000", "0.0199", "300"),
            debt("Emprestimo", "4000", "0.0125", "250"),
            debt("Parcelado", "2000", "0.0099", "200"),
            debt("Loja", "800", "0.005", "80", due_day=20),
        )
        avalanche = simulate(PlanInput(Decimal("1200"), debts, "avalanche", start_month=START))
        snowball = simulate(PlanInput(Decimal("1200"), debts, "snowball", start_month=START))
        hybrid = simulate(PlanInput(Decimal("1200"), debts, "hybrid", start_month=START))
        self.assertEqual(avalanche.total_interest, Decimal("1230.45"))
        self.assertEqual(snowball.total_interest, Decimal("1426.83"))
        self.assertEqual(hybrid.total_interest, Decimal("1288.01"))
        self.assertTrue(hybrid.has_quick_wins)
        self.assertEqual(hybrid.first_payoff.debt_id, "Loja")
        self.assertEqual(hybrid.first_payoff.month_index, 2)

    def test_textbook_snowball(self):
        debts = (
            debt("A", "250", "0", "25", 1),
            debt("B", "500", "0", "26", 1),
            debt("C", "2500", "0", "150", 1),
            debt("D", "5000", "0", "200", 1),
        )
        result = simulate(PlanInput(Decimal("501"), debts, "snowball", start_month=START))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.months, 17)
        self.assertEqual(result.total_interest, Decimal("0.00"))
        self.assertEqual(result.total_paid, Decimal("8250.00"))
        self.assertEqual(result.debt_free_date, date(2027, 6, 1))


class EdgeCaseTests(SimpleTestCase):
    def test_infeasible_when_minimums_exceed_budget(self):
        result = simulate(
            PlanInput(
                Decimal("500"),
                (debt("A", "1000", "0.01", "500"), debt("B", "1000", "0.01", "250")),
                "avalanche",
                start_month=START,
            )
        )
        self.assertEqual(result.status, "infeasible")
        self.assertIn("mínimas", result.infeasible_reason)

    def test_negative_amortization_warning(self):
        result = simulate(
            PlanInput(
                Decimal("150"),
                (debt("A", "1000", "0.10", "100"),),
                "avalanche",
                start_month=START,
            )
        )
        codes = {warning.code for warning in result.warnings}
        self.assertIn("W_NEGATIVE_AMORT", codes)

    def test_term_exceeded(self):
        result = simulate(
            PlanInput(
                Decimal("10"),
                (debt("A", "1000", "0.02", "10"),),
                "avalanche",
                start_month=START,
                max_months=12,
            )
        )
        self.assertEqual(result.status, "term_exceeded")
        self.assertIn("W_TERM_EXCEEDED", {w.code for w in result.warnings})

    def test_extra_payment_reduces_term(self):
        base = simulate(
            PlanInput(
                Decimal("300"),
                (debt("A", "1000", "0.02", "100"),),
                "avalanche",
                start_month=START,
            )
        )
        extra = simulate(
            PlanInput(
                Decimal("300"),
                (debt("A", "1000", "0.02", "100"),),
                "avalanche",
                start_month=START,
                extra_payment=Decimal("100"),
                extra_payment_months=1,
            )
        )
        self.assertLessEqual(extra.months, base.months)
        self.assertLessEqual(extra.total_interest, base.total_interest)

    def test_deterministic(self):
        debts = (
            debt("A", "100", "0.02", "50"),
            debt("B", "100", "0.02", "50"),
        )
        first = simulate(PlanInput(Decimal("200"), debts, "avalanche", start_month=START))
        second = simulate(PlanInput(Decimal("200"), debts, "avalanche", start_month=START))
        self.assertEqual(first, second)

    def test_comparison_recommends_hybrid_with_quick_win(self):
        debts = (
            debt("Cartao", "6000", "0.0199", "300"),
            debt("Loja", "800", "0.005", "80"),
        )
        comparison = compare_strategies(
            PlanInput(Decimal("800"), debts, "hybrid", start_month=START)
        )
        self.assertEqual(comparison["recommendation"], "hybrid")
        self.assertEqual(comparison["strategies"]["hybrid"]["status"], "ok")
