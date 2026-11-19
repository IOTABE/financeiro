from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

from apps.debts.models import Debt

User = get_user_model()


class Plan(models.Model):
    class Strategy(models.TextChoices):
        AVALANCHE = "avalanche", "Avalanche"
        SNOWBALL = "snowball", "Snowball"
        HYBRID = "hybrid", "Híbrida"

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        ARCHIVED = "archived", "Arquivado"
        STALE = "stale", "Desatualizado"
        INFEASIBLE = "infeasible", "Inviável"
        TERM_EXCEEDED = "term_exceeded", "Prazo excedido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="plans", verbose_name="usuário"
    )
    label = models.CharField("rótulo", max_length=80, blank=True)
    strategy = models.CharField("estratégia", max_length=12, choices=Strategy.choices)
    status = models.CharField(
        "status", max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    engine_version = models.CharField("versão do motor", max_length=20)
    input_snapshot = models.JSONField("snapshot de entrada", default=dict)
    summary = models.JSONField("resumo", default=dict)
    monthly_available = models.DecimalField(
        "disponível mensal", max_digits=14, decimal_places=2, default=0
    )
    total_interest = models.DecimalField(
        "juros projetados", max_digits=14, decimal_places=2, default=0
    )
    total_paid = models.DecimalField("total pago", max_digits=14, decimal_places=2, default=0)
    months_to_payoff = models.PositiveSmallIntegerField("meses até quitar", null=True, blank=True)
    debt_free_date = models.DateField("livre de dívidas em", null=True, blank=True)
    infeasible_reason = models.CharField("motivo de inviabilidade", max_length=300, blank=True)
    generated_at = models.DateTimeField("gerado em", auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plano"
        verbose_name_plural = "planos"
        ordering = ("-generated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="active"),
                name="uq_plan_active_user",
            ),
            models.CheckConstraint(
                condition=Q(strategy__in=["avalanche", "snowball", "hybrid"]),
                name="ck_plan_strategy",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["active", "archived", "stale", "infeasible", "term_exceeded"]
                ),
                name="ck_plan_status",
            ),
        ]
        indexes = [models.Index(fields=["user", "generated_at"])]

    def __str__(self) -> str:
        return f"Plano {self.get_strategy_display()} ({self.generated_at:%d/%m/%Y})"

    @property
    def is_feasible(self) -> bool:
        return self.status in {self.Status.ACTIVE, self.Status.STALE}

    @property
    def is_current(self) -> bool:
        return self.status in {self.Status.ACTIVE, self.Status.STALE}


class PlanItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="items", verbose_name="plano"
    )
    debt = models.ForeignKey(
        Debt, on_delete=models.SET_NULL, null=True, related_name="plan_items", verbose_name="dívida"
    )
    priority_order = models.PositiveSmallIntegerField("ordem")
    reason = models.CharField("justificativa", max_length=240)
    projected_payoff_month = models.DateField("quitação projetada", null=True, blank=True)
    projected_interest = models.DecimalField(
        "juros projetados", max_digits=14, decimal_places=2, default=0
    )
    projected_total_paid = models.DecimalField(
        "total pago projetado", max_digits=14, decimal_places=2, default=0
    )
    debt_name = models.CharField("nome da dívida", max_length=160, blank=True)

    class Meta:
        verbose_name = "item do plano"
        verbose_name_plural = "itens do plano"
        ordering = ("priority_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "priority_order"], name="uq_plan_item_priority"
            ),
            models.CheckConstraint(
                condition=Q(priority_order__gte=1), name="ck_plan_item_priority"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.priority_order}. {self.debt_name or self.debt}"


class PlanSchedule(models.Model):
    id = models.BigAutoField(primary_key=True)
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="schedule", verbose_name="plano"
    )
    debt = models.ForeignKey(
        Debt, on_delete=models.SET_NULL, null=True, related_name="schedules", verbose_name="dívida"
    )
    debt_name = models.CharField("nome da dívida", max_length=160, blank=True)
    competence_month = models.DateField("competência")
    payment = models.DecimalField("pagamento", max_digits=14, decimal_places=2)
    interest = models.DecimalField("juros", max_digits=14, decimal_places=2)
    principal = models.DecimalField("principal", max_digits=14, decimal_places=2)
    capitalized_interest = models.DecimalField(
        "juros capitalizados", max_digits=14, decimal_places=2, default=0
    )
    closing_balance = models.DecimalField("saldo final", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "calendário do plano"
        verbose_name_plural = "calendários do plano"
        ordering = ("competence_month", "plan", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "debt", "competence_month"],
                name="uq_plan_schedule_debt_month",
            ),
            models.CheckConstraint(
                condition=Q(payment__gte=0)
                & Q(interest__gte=0)
                & Q(principal__gte=0)
                & Q(capitalized_interest__gte=0)
                & Q(closing_balance__gte=0),
                name="ck_plan_schedule_values",
            ),
            models.CheckConstraint(
                condition=Q(principal=0) | Q(capitalized_interest=0),
                name="ck_plan_schedule_capitalized",
            ),
        ]
        indexes = [models.Index(fields=["plan", "competence_month"])]

    def __str__(self) -> str:
        return f"{self.competence_month:%m/%Y} · {self.payment}"

    @property
    def is_paid(self) -> bool:
        return hasattr(self, "adherence")


class PlanPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="plan_payments", verbose_name="usuário"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="payments", verbose_name="plano"
    )
    schedule = models.OneToOneField(
        PlanSchedule,
        on_delete=models.CASCADE,
        related_name="adherence",
        verbose_name="parcela planejada",
    )
    amount = models.DecimalField("valor pago", max_digits=14, decimal_places=2)
    paid_at = models.DateField("pago em")
    note = models.CharField("observação", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pagamento do plano"
        verbose_name_plural = "pagamentos do plano"
        ordering = ("-paid_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="ck_plan_payment_amount_positive"
            )
        ]
        indexes = [
            models.Index(fields=["user", "paid_at"]),
            models.Index(fields=["plan", "paid_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.plan} · {self.schedule.competence_month:%m/%Y} · {self.amount}"


class Simulation(models.Model):
    class Kind(models.TextChoices):
        EXPENSE_CUT = "expense_cut", "Corte de despesa"
        EXTRA_INCOME = "extra_income", "Renda extra"
        RENEGOTIATION = "renegotiation", "Renegociação"
        CONSERVATIVE = "conservative", "Cenário conservador"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="simulations", verbose_name="usuário"
    )
    base_plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="simulations",
        verbose_name="plano base",
    )
    name = models.CharField("nome", max_length=80)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    params = models.JSONField("parâmetros", default=dict)
    result_summary = models.JSONField("resultado", default=dict)
    engine_version = models.CharField("versão do motor", max_length=20)
    applied_at = models.DateTimeField("aplicado em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "simulação"
        verbose_name_plural = "simulações"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    kind__in=["expense_cut", "extra_income", "renegotiation", "conservative"]
                ),
                name="ck_simulation_kind",
            )
        ]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self) -> str:
        return self.name
