from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

User = get_user_model()

ZERO = Decimal("0")


class Category(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="categories", verbose_name="usuário"
    )
    name = models.CharField("nome", max_length=80)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    is_essential = models.BooleanField("essencial", default=False)
    color = models.CharField("cor", max_length=7, blank=True)
    icon = models.CharField("ícone", max_length=40, blank=True)
    is_system = models.BooleanField("padrão do sistema", default=False)
    archived_at = models.DateTimeField("arquivada em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ("kind", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "user",
                "kind",
                condition=Q(archived_at__isnull=True),
                name="uq_category_user_kind_name",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["income", "expense"]), name="ck_category_kind"
            ),
        ]
        indexes = [models.Index(fields=["user", "kind", "archived_at"])]

    def __str__(self) -> str:
        return self.name


class Account(models.Model):
    class Type(models.TextChoices):
        CHECKING = "checking", "Conta corrente"
        SAVINGS = "savings", "Poupança"
        CASH = "cash", "Dinheiro"
        CREDIT_CARD = "credit_card", "Cartão de crédito"
        INVESTMENT = "investment", "Investimento"
        OTHER = "other", "Outra"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="accounts", verbose_name="usuário"
    )
    name = models.CharField("nome", max_length=80)
    type = models.CharField("tipo", max_length=20, choices=Type.choices, default=Type.CHECKING)
    opening_balance = models.DecimalField(
        "saldo inicial",
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(Decimal("-999999999999.99"))],
    )
    archived_at = models.DateTimeField("arquivada em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conta"
        verbose_name_plural = "contas"
        ordering = ("name",)
        indexes = [models.Index(fields=["user", "archived_at"])]

    def __str__(self) -> str:
        return self.name


class InstallmentGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="installment_groups", verbose_name="usuário"
    )
    description = models.CharField("descrição", max_length=140)
    total_amount = models.DecimalField(
        "valor total",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    installments = models.PositiveSmallIntegerField(
        "parcelas", validators=[MinValueValidator(2), MaxValueValidator(360)]
    )
    first_due_date = models.DateField("primeiro vencimento")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="installment_groups",
        verbose_name="categoria",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="installment_groups",
        verbose_name="conta",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "compra parcelada"
        verbose_name_plural = "compras parceladas"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount__gt=0), name="ck_installment_total_positive"
            ),
            models.CheckConstraint(
                condition=Q(installments__gte=2) & Q(installments__lte=360),
                name="ck_installment_count",
            ),
        ]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self) -> str:
        return f"{self.description} ({self.installments}x)"


class Recurrence(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recurrences", verbose_name="usuário"
    )
    description = models.CharField("descrição", max_length=140)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    amount = models.DecimalField(
        "valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    frequency = models.CharField("frequência", max_length=16, default="monthly")
    due_day = models.PositiveSmallIntegerField(
        "dia de vencimento", validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    start_date = models.DateField("início")
    end_date = models.DateField("fim", null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurrences",
        verbose_name="categoria",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurrences",
        verbose_name="conta",
    )
    next_run = models.DateField("próxima competência")
    is_active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "recorrência"
        verbose_name_plural = "recorrências"
        ordering = ("description",)
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_recurrence_amount_positive"),
            models.CheckConstraint(
                condition=Q(due_day__gte=1) & Q(due_day__lte=31), name="ck_recurrence_due_day"
            ),
        ]
        indexes = [models.Index(fields=["user", "is_active", "next_run"])]

    def __str__(self) -> str:
        return self.description


class Transaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Pago"
        CANCELED = "canceled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transactions", verbose_name="usuário"
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="conta",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="categoria",
    )
    recurrence = models.ForeignKey(
        Recurrence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="recorrência",
    )
    installment_group = models.ForeignKey(
        InstallmentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="parcelamento",
    )
    installment_number = models.PositiveSmallIntegerField(
        "número da parcela", null=True, blank=True
    )
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    amount = models.DecimalField(
        "valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.CharField("descrição", max_length=200, blank=True)
    transaction_date = models.DateField("data")
    competence_month = models.DateField("competência")
    status = models.CharField(
        "status", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    paid_at = models.DateField("pago em", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    tags = models.JSONField("tags", default=list, blank=True)
    idempotency_key = models.CharField("chave de idempotência", max_length=80, blank=True)
    deleted_at = models.DateTimeField("excluída em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "transação"
        verbose_name_plural = "transações"
        ordering = ("-transaction_date", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="ck_transaction_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["income", "expense"]), name="ck_transaction_kind"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "paid", "canceled"]),
                name="ck_transaction_status",
            ),
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(paid_at__isnull=False),
                name="ck_transaction_paid_at",
            ),
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=Q(idempotency_key__gt="", deleted_at__isnull=True),
                name="uq_transaction_user_idempotency",
            ),
            models.UniqueConstraint(
                fields=["recurrence", "competence_month"],
                condition=Q(recurrence__isnull=False, deleted_at__isnull=True),
                name="uq_transaction_recurrence_competence",
            ),
            models.UniqueConstraint(
                fields=["installment_group", "installment_number"],
                condition=Q(installment_group__isnull=False, deleted_at__isnull=True),
                name="uq_transaction_installment_number",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "deleted_at", "transaction_date"]),
            models.Index(fields=["user", "competence_month", "status"]),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "account"]),
        ]

    def __str__(self) -> str:
        label = self.description or self.get_kind_display()
        return f"{label} · {self.amount}"

    def save(self, *args, **kwargs):
        if not self.competence_month:
            self.competence_month = self.transaction_date.replace(day=1)
        if self.status == self.Status.PAID and not self.paid_at:
            self.paid_at = self.transaction_date
        super().save(*args, **kwargs)
