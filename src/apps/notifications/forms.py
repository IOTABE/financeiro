from __future__ import annotations

from django import forms

from apps.core.forms import StyledFormMixin

from .models import NotificationPreference


class NotificationPreferenceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = (
            "email_enabled",
            "due_reminders",
            "weekly_summary",
            "risk_alerts",
            "quiet_hours_start",
            "quiet_hours_end",
        )
        labels = {
            "email_enabled": "Receber e-mails",
            "due_reminders": "Lembretes de vencimento",
            "weekly_summary": "Resumo semanal",
            "risk_alerts": "Alertas de risco",
            "quiet_hours_start": "Início do horário de silêncio",
            "quiet_hours_end": "Fim do horário de silêncio",
        }
        widgets = {
            "quiet_hours_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_hours_end": forms.TimeInput(attrs={"type": "time"}),
        }
