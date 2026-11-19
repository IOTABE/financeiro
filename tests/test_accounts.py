from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Consent, Profile

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_normalizes_email_and_creates_profile(self):
        user = User.objects.create_user(email="ANA@Example.com", password="senha-forte-123")
        self.assertEqual(user.email, "ana@example.com")
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(user.check_password("senha-forte-123"))

    def test_create_superuser_has_expected_flags(self):
        user = User.objects.create_superuser(email="admin@example.com", password="senha-forte-123")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class RegisterViewTests(TestCase):
    def setUp(self):
        self.url = reverse("accounts:register")
        self.payload = {
            "full_name": "Ana Souza",
            "email": "ana@example.com",
            "password1": "UmaSenhaMuitoForte123",
            "password2": "UmaSenhaMuitoForte123",
            "accept_terms": "on",
            "accept_privacy": "on",
        }

    def test_register_creates_user_profile_and_consents(self):
        response = self.client.post(self.url, self.payload)
        self.assertRedirects(response, reverse("core:dashboard"))
        user = User.objects.get(email="ana@example.com")
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(Consent.objects.filter(user=user).count(), 2)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_register_requires_consents(self):
        payload = {**self.payload, "accept_terms": "", "accept_privacy": ""}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Você precisa aceitar os termos")
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este e-mail já está em uso")
        self.assertEqual(User.objects.filter(email="ana@example.com").count(), 1)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ana@example.com", password="UmaSenhaMuitoForte123"
        )

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "ana@example.com", "password": "UmaSenhaMuitoForte123"},
        )
        self.assertRedirects(response, reverse("core:dashboard"))

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "ana@example.com", "password": "errada"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail ou senha inválidos")


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ana@example.com", password="UmaSenhaMuitoForte123"
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_update_profile_and_complete_onboarding(self):
        response = self.client.post(
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
        self.assertRedirects(response, reverse("core:dashboard"))
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.net_income, Decimal("4200.00"))
        self.assertEqual(profile.essential_expenses, Decimal("2600.00"))
        self.assertIsNotNone(profile.onboarding_completed_at)

    def test_profile_rejects_essentials_above_income(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "net_income": "1000.00",
                "essential_expenses": "1500.00",
                "other_planned_expenses": "0.00",
                "income_type": "fixed",
                "conservative_factor": "0.800",
                "dependents": "0",
                "theme": "system",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não podem ser maiores que a renda")
