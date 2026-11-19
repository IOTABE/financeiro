from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.core.forms import StyledFormMixin
from apps.debts.models import Debt

from .models import Plan, Simulation


class PlanGenerateForm(StyledFormMixin, forms.Form):
    strategy = forms.ChoiceField(
        label="Estratégia",
        choices=Plan.Strategy.choices,
        initial=Plan.Strategy.HYBRID,
        help_text="A híbrida combina vitórias rápidas com a maior taxa; a avalanche foca juros.",
    )
    start_month = forms.DateField(
        label="Mês inicial",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    extra_payment = forms.DecimalField(
        label="Aporte extra (opcional)",
        max_digits=14,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
    )
    extra_payment_months = forms.IntegerField(
        label="Meses do aporte (0 = único)",
        required=False,
        min_value=0,
        max_value=120,
        initial=0,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_month"].initial = timezone.localdate().replace(day=1)
        self.fields["extra_payment"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
        )
        self.fields["extra_payment_months"].widget.attrs.update({"min": "0", "max": "120"})

    def clean(self):
        cleaned = super().clean()
        extra = cleaned.get("extra_payment") or Decimal("0")
        months = cleaned.get("extra_payment_months") or 0
        if extra < 0 or months < 0:
            raise forms.ValidationError("O aporte extra e os meses não podem ser negativos.")
        cleaned["extra_payment"] = extra
        cleaned["extra_payment_months"] = months
        return cleaned


class SimulationForm(StyledFormMixin, forms.Form):
    kind = forms.ChoiceField(label="Cenário", choices=Simulation.Kind.choices)
    name = forms.CharField(label="Nome do cenário", max_length=80)

    expense_cut = forms.DecimalField(
        label="Corte mensal de despesa",
        max_digits=14,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.01"),
    )
    extra_income = forms.DecimalField(
        label="Renda extra",
        max_digits=14,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.01"),
    )
    extra_income_months = forms.IntegerField(
        label="Meses de renda extra (0 = único)",
        required=False,
        min_value=0,
        max_value=120,
        initial=0,
    )

    debt_id = forms.ModelChoiceField(
        label="Dívida",
        queryset=Debt.objects.none(),
        required=False,
    )
    new_rate_percent = forms.DecimalField(
        label="Nova taxa mensal (%)",
        max_digits=8,
        decimal_places=4,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    )
    new_term_months = forms.IntegerField(
        label="Novo prazo (meses)",
        required=False,
        min_value=1,
        max_value=360,
    )
    discount_percent = forms.DecimalField(
        label="Desconto sobre o saldo (%)",
        max_digits=6,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    )
    entry_payment = forms.DecimalField(
        label="Entrada (opcional)",
        max_digits=14,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
    )

    income_factor = forms.DecimalField(
        label="Fator de renda",
        max_digits=4,
        decimal_places=3,
        required=False,
        min_value=Decimal("0.300"),
        max_value=Decimal("1.000"),
        initial=Decimal("0.800"),
    )
    expense_factor = forms.DecimalField(
        label="Fator de despesa",
        max_digits=4,
        decimal_places=3,
        required=False,
        min_value=Decimal("1.000"),
        max_value=Decimal("2.000"),
        initial=Decimal("1.100"),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["debt_id"].queryset = Debt.objects.filter(
            user=user,
            status__in=[Debt.Status.ACTIVE, Debt.Status.LATE],
            deleted_at__isnull=True,
        ).order_by("due_day", "-current_balance")
        for field_name in ("expense_cut", "extra_income", "entry_payment"):
            self.fields[field_name].widget.attrs.update(
                {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            )
        self.fields["new_rate_percent"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "1,99"}
        )
        self.fields["discount_percent"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
        )
        self.fields["extra_income_months"].widget.attrs.update({"min": "0", "max": "120"})
        self.fields["new_term_months"].widget.attrs.update({"min": "1", "max": "360"})
        if not self.initial.get("name"):
            self.initial["name"] = "Meu cenário"

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind == Simulation.Kind.EXPENSE_CUT and not cleaned.get("expense_cut"):
            self.add_error("expense_cut", "Informe o valor do corte mensal.")
        if kind == Simulation.Kind.EXTRA_INCOME and not cleaned.get("extra_income"):
            self.add_error("extra_income", "Informe o valor da renda extra.")
        if kind == Simulation.Kind.RENEGOTIATION and not cleaned.get("debt_id"):
            self.add_error("debt_id", "Escolha a dívida que será renegociada.")
        return cleaned

    def get_params(self) -> dict:
        kind = self.cleaned_data["kind"]
        data = self.cleaned_data
        if kind == Simulation.Kind.EXPENSE_CUT:
            return {"expense_cut": data["expense_cut"]}
        if kind == Simulation.Kind.EXTRA_INCOME:
            return {
                "extra_income": data["extra_income"],
                "extra_income_months": data.get("extra_income_months") or 0,
            }
        if kind == Simulation.Kind.RENEGOTIATION:
            return {
                "debt_id": str(data["debt_id"].pk) if data.get("debt_id") else "",
                "new_rate_percent": data.get("new_rate_percent"),
                "new_term_months": data.get("new_term_months") or 0,
                "discount_percent": data.get("discount_percent") or 0,
                "entry_payment": data.get("entry_payment") or 0,
            }
        return {
            "income_factor": data.get("income_factor") or Decimal("0.800"),
            "expense_factor": data.get("expense_factor") or Decimal("1.100"),
        }
