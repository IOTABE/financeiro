from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Email-first user manager (no username field)."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa ter is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField("nome completo", max_length=150, blank=True)
    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField("equipe", default=False)
    date_joined = models.DateTimeField("entrou em", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ("email",)

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    def get_short_name(self) -> str:
        return self.get_full_name().split(" ")[0]


class Profile(models.Model):
    class IncomeType(models.TextChoices):
        FIXED = "fixed", "Renda fixa"
        VARIABLE = "variable", "Renda variável"

    class Theme(models.TextChoices):
        SYSTEM = "system", "Seguir sistema"
        LIGHT = "light", "Claro"
        DARK = "dark", "Escuro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name="usuário"
    )
    currency = models.CharField("moeda", max_length=3, default="BRL")
    timezone = models.CharField("fuso horário", max_length=64, default="America/Sao_Paulo")
    gross_income = models.DecimalField(
        "renda bruta mensal",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    net_income = models.DecimalField(
        "renda líquida mensal",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    essential_expenses = models.DecimalField(
        "despesas essenciais",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    min_existential = models.DecimalField(
        "mínimo existencial",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    other_planned_expenses = models.DecimalField(
        "outras despesas planejadas",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    income_type = models.CharField(
        "tipo de renda",
        max_length=16,
        choices=IncomeType.choices,
        default=IncomeType.FIXED,
    )
    conservative_factor = models.DecimalField(
        "fator conservador",
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.800"),
        validators=[MinValueValidator(Decimal("0.300")), MaxValueValidator(Decimal("1.000"))],
        help_text="Usado para renda variável (ex.: 0,80 = 80% da média).",
    )
    dependents = models.PositiveSmallIntegerField("dependentes", default=0)
    theme = models.CharField("tema", max_length=8, choices=Theme.choices, default=Theme.SYSTEM)
    onboarding_completed_at = models.DateTimeField("onboarding concluído em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil financeiro"
        verbose_name_plural = "perfis financeiros"

    def __str__(self) -> str:
        return f"Perfil de {self.user.email}"

    @property
    def essential_floor(self) -> Decimal:
        essentials = self.essential_expenses or Decimal("0")
        minimum = self.min_existential or Decimal("0")
        return max(essentials, minimum)

    @property
    def has_income(self) -> bool:
        return bool(self.net_income and self.net_income > 0)


class Consent(models.Model):
    class Kind(models.TextChoices):
        TERMS = "terms", "Termos de uso"
        PRIVACY = "privacy", "Política de privacidade"
        TELEMETRY = "telemetry", "Telemetria"
        MARKETING = "marketing", "Comunicações"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="consents", verbose_name="usuário"
    )
    kind = models.CharField("tipo", max_length=32, choices=Kind.choices)
    version = models.CharField("versão", max_length=20, default="1.0")
    accepted = models.BooleanField("aceito", default=True)
    accepted_at = models.DateTimeField("aceito em", default=timezone.now)
    ip_hash = models.CharField("hash do IP", max_length=64, blank=True)
    user_agent_hash = models.CharField("hash do user-agent", max_length=64, blank=True)

    class Meta:
        verbose_name = "consentimento"
        verbose_name_plural = "consentimentos"
        ordering = ("-accepted_at",)
        indexes = [models.Index(fields=["user", "kind", "version"])]

    def __str__(self) -> str:
        return f"{self.user.email} · {self.kind} v{self.version}"
