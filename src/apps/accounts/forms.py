from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.core.forms import StyledFormMixin

from .models import Profile, User


class RegisterForm(StyledFormMixin, UserCreationForm):
    accept_terms = forms.BooleanField(
        label="Li e aceito os termos de uso",
        error_messages={"required": "Você precisa aceitar os termos de uso."},
    )
    accept_privacy = forms.BooleanField(
        label="Li e aceito a política de privacidade",
        error_messages={"required": "Você precisa aceitar a política de privacidade."},
    )

    class Meta:
        model = User
        fields = ("full_name", "email")
        labels = {"full_name": "Nome completo", "email": "E-mail"}
        widgets = {
            "full_name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "Como podemos te chamar?"}
            ),
            "email": forms.EmailInput(
                attrs={"autocomplete": "email", "placeholder": "voce@exemplo.com"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirme a senha"
        self.fields["password1"].widget.attrs.update(
            {"autocomplete": "new-password", "placeholder": "Mínimo de 10 caracteres"}
        )
        self.fields["password2"].widget.attrs.update(
            {"autocomplete": "new-password", "placeholder": "Repita a senha"}
        )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return email


class EmailAuthenticationForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "placeholder": "voce@exemplo.com"}
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "placeholder": "Sua senha"}
        ),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "E-mail ou senha inválidos.",
    }


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            "gross_income",
            "net_income",
            "essential_expenses",
            "min_existential",
            "other_planned_expenses",
            "income_type",
            "conservative_factor",
            "dependents",
            "theme",
        )
        labels = {
            "gross_income": "Renda bruta mensal",
            "net_income": "Renda líquida mensal",
            "essential_expenses": "Despesas essenciais mensais",
            "min_existential": "Mínimo existencial",
            "other_planned_expenses": "Outras despesas planejadas",
            "income_type": "Tipo de renda",
            "conservative_factor": "Fator conservador (renda variável)",
            "dependents": "Dependentes",
            "theme": "Tema da interface",
        }
        help_texts = {
            "gross_income": "Valor antes dos descontos. Usado para o DTI.",
            "net_income": "Valor que efetivamente entra na conta.",
            "essential_expenses": "Moradia, alimentação, transporte, saúde e contas básicas.",
            "min_existential": "Piso que você não quer comprometer. Usamos o maior valor entre este e as despesas essenciais.",
            "other_planned_expenses": "Gastos já planejados que não são essenciais.",
            "conservative_factor": "Ex.: 0,80 significa usar 80% da renda média.",
            "theme": "Escolha como a interface deve aparecer.",
        }
        widgets = {
            "gross_income": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "net_income": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "essential_expenses": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "min_existential": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "other_planned_expenses": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "conservative_factor": forms.NumberInput(
                attrs={"inputmode": "decimal", "step": "0.05", "min": "0.30", "max": "1.00"}
            ),
            "dependents": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }

    def clean(self):
        cleaned = super().clean()
        net = cleaned.get("net_income")
        essentials = cleaned.get("essential_expenses")
        minimum = cleaned.get("min_existential")
        if net is not None and essentials is not None and essentials > net:
            self.add_error(
                "essential_expenses",
                "As despesas essenciais não podem ser maiores que a renda líquida.",
            )
        if net is not None and minimum is not None and minimum > net:
            self.add_error(
                "min_existential",
                "O mínimo existencial não pode ser maior que a renda líquida.",
            )
        return cleaned


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="Senha atual",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirmation = forms.CharField(
        label="Digite EXCLUIR para confirmar",
        max_length=10,
    )

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip().upper()
        if value != "EXCLUIR":
            raise forms.ValidationError("Digite EXCLUIR para confirmar a exclusão.")
        return value
