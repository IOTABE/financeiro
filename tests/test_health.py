from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Profile
from apps.accounts.services import financial_health

User = get_user_model()


def make_profile(**kwargs) -> Profile:
    user = User.objects.create_user(email=f"user-{User.objects.count()}@example.com")
    profile = user.profile
    for key, value in kwargs.items():
        setattr(profile, key, value)
    profile.save()
    return profile


class FinancialHealthTests(TestCase):
    def test_uses_max_of_essentials_and_minimum(self):
        profile = make_profile(
            net_income=Decimal("4200.00"),
            gross_income=Decimal("5200.00"),
            essential_expenses=Decimal("2000.00"),
            min_existential=Decimal("2600.00"),
            other_planned_expenses=Decimal("200.00"),
        )
        health = financial_health(profile, Decimal("750.00"))
        self.assertEqual(health["essential_floor"], Decimal("2600.00"))
        self.assertEqual(health["debt_budget"], Decimal("1400.00"))
        self.assertEqual(health["free_cash"], Decimal("650.00"))
        self.assertEqual(health["risk_level"], "healthy")

    def test_commitment_above_30_percent_is_attention(self):
        profile = make_profile(
            net_income=Decimal("1000.00"),
            essential_expenses=Decimal("500.00"),
            min_existential=Decimal("500.00"),
        )
        health = financial_health(profile, Decimal("350.00"))
        self.assertEqual(health["risk_level"], "attention")
        self.assertEqual(health["commitment_ratio"], Decimal("0.35"))

    def test_negative_free_cash_is_critical(self):
        profile = make_profile(
            net_income=Decimal("1000.00"),
            essential_expenses=Decimal("1200.00"),
            min_existential=Decimal("1000.00"),
        )
        health = financial_health(profile, Decimal("0"))
        self.assertEqual(health["free_cash"], Decimal("-200.00"))
        self.assertEqual(health["risk_level"], "critical")

    def test_no_income_is_unknown(self):
        profile = make_profile(net_income=None)
        health = financial_health(profile)
        self.assertFalse(health["has_income"])
        self.assertEqual(health["risk_level"], "unknown")
        self.assertTrue(health["alerts"])
