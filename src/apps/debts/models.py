from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

User = get_user_model()

ZERO = Decimal("0")


class Debt(models.Model):
    class Type(models.TextChoices):
        CREDIT_CARD = "credit_card", "Cartão de crédito"
        OVERDRAFT = "overdraft", "Cheque especial"
        PERSONAL_LOAN = "personal_loan", "Empréstimo pessoal"
        PAYROLL_LOAN = "payroll_loan", "Consignado"
        INSTALLMENT = "installment", "Parcelado"
        MORTGAGE = "mortgage", "Financiamento"
        FAMILY = "family", "Família/amigos"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativa"
        PAID = "paid", "Quitada"
        RENEGOTIATED = "renegotiated", "Renegociada"
        LATE = "late", "Em atraso"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="debts", verbose_name="usuário"
    )
    creditor = models.CharField("credor", max_length=120)
    nickname = models.CharField("apelido", max_length=80, blank=True)
    type = models.CharField("tipo", max_length=24, choices=Type.choices, default=Type.OTHER)
    original_amount = models.DecimalField(
        "valor original",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    current_balance = models.DecimalField(
        "saldo devedor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    monthly_rate = models.DecimalField(
        "taxa mensal",
        max_digits=12,
        decimal_places=10,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    annual_rate = models.DecimalField(
        "taxa anual",
        max_digits=12,
        decimal_places=10,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    cet = models.DecimalField(
        "CET anual",
        max_digits=12,
        decimal_places=10,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    minimum_payment = models.DecimalField(
        "parcela mínima",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    installment_amount = models.DecimalField(
        "parcela contratada",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    due_day = models.PositiveSmallIntegerField(
        "dia de vencimento", validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    start_date = models.DateField("início", null=True, blank=True)
    status = models.CharField(
        "status", max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    priority_locked = models.PositiveSmallIntegerField("prioridade manual", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    deleted_at = models.DateTimeField("excluída em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "dívida"
        verbose_name_plural = "dívidas"
        ordering = ("-current_balance", "creditor")
        constraints = [
            models.CheckConstraint(
                condition=Q(current_balance__gte=0), name="ck_debt_balance_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(minimum_payment__gt=0), name="ck_debt_minimum_positive"
            ),
            models.CheckConstraint(
                condition=Q(monthly_rate__gte=0) & Q(monthly_rate__lte=1),
                name="ck_debt_monthly_rate",
            ),
            models.CheckConstraint(
                condition=Q(due_day__gte=1) & Q(due_day__lte=31), name="ck_debt_due_day"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["active", "paid", "renegotiated", "late"]),
                name="ck_debt_status",
            ),
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(current_balance=0),
                name="ck_debt_paid_balance",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status", "deleted_at"]),
            models.Index(fields=["user", "priority_locked"]),
        ]

    def __str__(self) -> str:
        return self.nickname or self.creditor

    @property
    def interest_at_minimum(self) -> Decimal:
        return (self.current_balance * self.monthly_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def has_negative_amortization(self) -> bool:
        return self.minimum_payment <= self.interest_at_minimum

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.ACTIVE, self.Status.LATE} and self.current_balance > 0


class DebtPayment(models.Model):
    class Kind(models.TextChoices):
        MINIMUM = "minimum", "Mínimo"
        INSTALLMENT = "installment", "Parcela"
        EXTRA = "extra", "Extra"
        SETTLEMENT = "settlement", "Quitação"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="debt_payments", verbose_name="usuário"
    )
    debt = models.ForeignKey(
        Debt, on_delete=models.CASCADE, related_name="payments", verbose_name="dívida"
    )
    amount = models.DecimalField(
        "valor pago",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    principal_amount = models.DecimalField(
        "principal", max_digits=14, decimal_places=2, default=ZERO
    )
    interest_amount = models.DecimalField("juros", max_digits=14, decimal_places=2, default=ZERO)
    paid_at = models.DateField("pago em")
    kind = models.CharField("tipo", max_length=16, choices=Kind.choices, default=Kind.MINIMUM)
    note = models.CharField("observação", max_length=200, blank=True)
    idempotency_key = models.CharField("chave de idempotência", max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pagamento de dívida"
        verbose_name_plural = "pagamentos de dívidas"
        ordering = ("-paid_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="ck_debt_payment_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["minimum", "installment", "extra", "settlement"]),
                name="ck_debt_payment_kind",
            ),
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=Q(idempotency_key__gt=""),
                name="uq_debt_payment_user_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["debt", "paid_at"]),
            models.Index(fields=["user", "paid_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.debt} · {self.amount}"
