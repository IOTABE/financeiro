from __future__ import annotations

import uuid
from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.core.forms import StyledFormMixin

from .models import Debt, DebtPayment


class DebtForm(StyledFormMixin, forms.ModelForm):
    monthly_rate_percent = forms.DecimalField(
        label="Taxa mensal (%)",
        max_digits=8,
        decimal_places=4,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        help_text="Ex.: 1,99. Preencha a taxa mensal ou a anual.",
    )
    annual_rate_percent = forms.DecimalField(
        label="Taxa anual efetiva (%)",
        max_digits=10,
        decimal_places=4,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("1000"),
        help_text="Ex.: 26,82. Convertemos para mensal por juros compostos.",
    )
    cet_percent = forms.DecimalField(
        label="CET anual (%)",
        max_digits=10,
        decimal_places=4,
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("1000"),
    )

    class Meta:
        model = Debt
        fields = (
            "creditor",
            "nickname",
            "type",
            "original_amount",
            "current_balance",
            "minimum_payment",
            "installment_amount",
            "due_day",
            "start_date",
            "status",
            "notes",
        )
        labels = {
            "creditor": "Credor",
            "nickname": "Apelido",
            "type": "Tipo",
            "original_amount": "Valor original",
            "current_balance": "Saldo devedor atual",
            "minimum_payment": "Parcela mínima",
            "installment_amount": "Parcela contratada",
            "due_day": "Dia de vencimento",
            "start_date": "Início",
            "status": "Status",
            "notes": "Observações",
        }
        widgets = {
            "original_amount": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "current_balance": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "minimum_payment": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
            ),
            "installment_amount": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
            ),
            "due_day": forms.NumberInput(attrs={"min": "1", "max": "31"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monthly_rate_percent"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "1,99"}
        )
        self.fields["annual_rate_percent"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "26,82"}
        )
        self.fields["cet_percent"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "Opcional"}
        )
        if not self.instance._state.adding:
            self.initial["monthly_rate_percent"] = (self.instance.monthly_rate * 100).quantize(
                Decimal("0.0001")
            )
            if self.instance.annual_rate is not None:
                self.initial["annual_rate_percent"] = (self.instance.annual_rate * 100).quantize(
                    Decimal("0.0001")
                )
            if self.instance.cet is not None:
                self.initial["cet_percent"] = (self.instance.cet * 100).quantize(Decimal("0.0001"))

    def clean(self):
        cleaned = super().clean()
        monthly_percent = cleaned.get("monthly_rate_percent")
        annual_percent = cleaned.get("annual_rate_percent")
        if monthly_percent is None and annual_percent is None:
            self.add_error(
                "monthly_rate_percent",
                "Informe a taxa mensal ou a taxa anual efetiva.",
            )
            return cleaned

        if monthly_percent is not None:
            monthly = (monthly_percent / Decimal("100")).quantize(Decimal("0.0000000001"))
        else:
            annual = annual_percent / Decimal("100")
            monthly = ((Decimal(1) + annual) ** (Decimal(1) / Decimal(12)) - Decimal(1)).quantize(
                Decimal("0.0000000001")
            )
        cleaned["monthly_rate"] = monthly

        if annual_percent is not None:
            cleaned["annual_rate"] = (annual_percent / Decimal("100")).quantize(
                Decimal("0.0000000001")
            )
        else:
            cleaned["annual_rate"] = None

        cet_percent = cleaned.get("cet_percent")
        cleaned["cet"] = (
            (cet_percent / Decimal("100")).quantize(Decimal("0.0000000001"))
            if cet_percent is not None
            else None
        )

        balance = cleaned.get("current_balance")
        status = cleaned.get("status")
        if status == Debt.Status.PAID and balance and balance > 0:
            self.add_error(
                "current_balance",
                "Uma dívida quitada precisa ter saldo devedor igual a zero.",
            )
        return cleaned

    def save(self, commit=True):
        debt = super().save(commit=False)
        debt.monthly_rate = self.cleaned_data["monthly_rate"]
        debt.annual_rate = self.cleaned_data["annual_rate"]
        debt.cet = self.cleaned_data["cet"]
        if commit:
            debt.save()
        return debt


class DebtPaymentForm(StyledFormMixin, forms.Form):
    amount = forms.DecimalField(
        label="Valor pago",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    paid_at = forms.DateField(
        label="Data do pagamento", widget=forms.DateInput(attrs={"type": "date"})
    )
    kind = forms.ChoiceField(label="Tipo", choices=DebtPayment.Kind.choices)
    note = forms.CharField(label="Observação", max_length=200, required=False)
    idempotency_key = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
        )
        self.initial.setdefault("paid_at", timezone.localdate())
        self.initial.setdefault("kind", DebtPayment.Kind.MINIMUM)
        self.initial.setdefault("idempotency_key", uuid.uuid4().hex)
