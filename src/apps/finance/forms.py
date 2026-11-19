from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.core.forms import StyledFormMixin

from .models import Account, Category, Recurrence, Transaction
from .services import create_installment_plan, create_recurrence, first_due_date


class UserScopedFormMixin(StyledFormMixin):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(
                user=user, archived_at__isnull=True
            )
            self.fields["category"].required = False
        if "account" in self.fields:
            self.fields["account"].queryset = Account.objects.filter(
                user=user, archived_at__isnull=True
            )
            self.fields["account"].required = False


class CategoryForm(UserScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "kind", "is_essential", "color")
        labels = {
            "name": "Nome",
            "kind": "Tipo",
            "is_essential": "Essencial",
            "color": "Cor (hex)",
        }
        widgets = {"color": forms.TextInput(attrs={"placeholder": "#0F766E"})}

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("name")
        kind = cleaned.get("kind")
        if name and kind:
            duplicate = Category.objects.filter(
                user=self.user, kind=kind, archived_at__isnull=True, name__iexact=name.strip()
            )
            if not self.instance._state.adding:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("name", "Já existe uma categoria com esse nome e tipo.")
        return cleaned

    def save(self, commit=True):
        category = super().save(commit=False)
        category.user = self.user
        if commit:
            category.save()
        return category


class AccountForm(UserScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Account
        fields = ("name", "type", "opening_balance")
        labels = {"name": "Nome", "type": "Tipo", "opening_balance": "Saldo inicial"}

    def save(self, commit=True):
        account = super().save(commit=False)
        account.user = self.user
        if commit:
            account.save()
        return account


class TransactionForm(UserScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = (
            "kind",
            "amount",
            "description",
            "transaction_date",
            "category",
            "account",
            "status",
        )
        labels = {
            "kind": "Tipo",
            "amount": "Valor",
            "description": "Descrição",
            "transaction_date": "Data",
            "category": "Categoria",
            "account": "Conta",
            "status": "Status",
        }
        widgets = {
            "amount": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
            ),
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.instance._state.adding:
            self.initial.setdefault("transaction_date", timezone.localdate())
            self.initial.setdefault("status", Transaction.Status.PAID)

    def save(self, commit=True):
        transaction = super().save(commit=False)
        transaction.user = self.user
        if transaction.status == Transaction.Status.PAID and not transaction.paid_at:
            transaction.paid_at = transaction.transaction_date
        elif transaction.status != Transaction.Status.PAID:
            transaction.paid_at = None
        if commit:
            if not transaction.competence_month:
                transaction.competence_month = transaction.transaction_date.replace(day=1)
            transaction.save()
        return transaction


class InstallmentForm(UserScopedFormMixin, forms.Form):
    kind = forms.ChoiceField(label="Tipo", choices=Transaction.Kind.choices)
    description = forms.CharField(label="Descrição", max_length=140)
    total_amount = forms.DecimalField(
        label="Valor total", max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    installments = forms.IntegerField(label="Parcelas", min_value=2, max_value=360, initial=2)
    first_due_date = forms.DateField(
        label="Primeiro vencimento", widget=forms.DateInput(attrs={"type": "date"})
    )
    category = forms.ModelChoiceField(
        label="Categoria", queryset=Category.objects.none(), required=False
    )
    account = forms.ModelChoiceField(label="Conta", queryset=Account.objects.none(), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["total_amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
        )
        self.fields["installments"].widget.attrs.update({"min": "2", "max": "360"})
        if not self.initial.get("first_due_date"):
            self.initial["first_due_date"] = timezone.localdate()

    def save(self):
        return create_installment_plan(
            user=self.user,
            description=self.cleaned_data["description"],
            total_amount=self.cleaned_data["total_amount"],
            installments=self.cleaned_data["installments"],
            first_due_date=self.cleaned_data["first_due_date"],
            kind=self.cleaned_data["kind"],
            category=self.cleaned_data["category"],
            account=self.cleaned_data["account"],
        )


class RecurrenceForm(UserScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Recurrence
        fields = (
            "description",
            "kind",
            "amount",
            "due_day",
            "start_date",
            "end_date",
            "category",
            "account",
            "is_active",
        )
        labels = {
            "description": "Descrição",
            "kind": "Tipo",
            "amount": "Valor",
            "due_day": "Dia de vencimento",
            "start_date": "Início",
            "end_date": "Fim (opcional)",
            "category": "Categoria",
            "account": "Conta",
            "is_active": "Ativa",
        }
        widgets = {
            "amount": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0.01", "placeholder": "0,00"}
            ),
            "due_day": forms.NumberInput(attrs={"min": "1", "max": "31"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.instance._state.adding:
            self.initial.setdefault("start_date", timezone.localdate())
            self.initial.setdefault("is_active", True)

    def save(self, commit=True):
        data = self.cleaned_data
        if not self.instance._state.adding:
            recurrence = self.instance
            old_start = recurrence.start_date
            old_due = recurrence.due_day
            for field in (
                "description",
                "kind",
                "amount",
                "due_day",
                "start_date",
                "end_date",
                "category",
                "account",
                "is_active",
            ):
                setattr(recurrence, field, data[field])
            if recurrence.start_date != old_start or recurrence.due_day != old_due:
                recurrence.next_run = first_due_date(recurrence.start_date, recurrence.due_day)
            if commit:
                recurrence.save()
            return recurrence

        recurrence = create_recurrence(
            user=self.user,
            description=data["description"],
            kind=data["kind"],
            amount=data["amount"],
            due_day=data["due_day"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            category=data["category"],
            account=data["account"],
            is_active=data["is_active"],
        )
        self.instance = recurrence
        return recurrence
