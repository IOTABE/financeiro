from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PublicPagesTests(TestCase):
    def test_landing_is_public(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saia do vermelho")

    def test_style_guide_is_public(self):
        response = self.client.get(reverse("core:style_guide"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Material 3 + Glassmorphism")

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readyz(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"]["database"], "ok")


class DashboardTests(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_authenticated_user_sees_empty_state_without_income(self):
        user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        self.client.force_login(user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe sua renda para começar")

    def test_authenticated_user_with_income_sees_free_cash(self):
        user = User.objects.create_user(email="ana@example.com", password="senha-forte-123")
        profile = user.profile
        profile.net_income = "4200.00"
        profile.essential_expenses = "2600.00"
        profile.min_existential = "1800.00"
        profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 1.600,00")
