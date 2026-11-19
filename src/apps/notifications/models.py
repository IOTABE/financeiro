from __future__ import annotations

import uuid
from datetime import time

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from django.utils import timezone

User = get_user_model()


class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name="usuário",
    )
    email_enabled = models.BooleanField("e-mails habilitados", default=True)
    due_reminders = models.BooleanField("lembretes de vencimento", default=True)
    weekly_summary = models.BooleanField("resumo semanal", default=False)
    risk_alerts = models.BooleanField("alertas de risco", default=True)
    quiet_hours_start = models.TimeField("início do silêncio", default=time(22, 0))
    quiet_hours_end = models.TimeField("fim do silêncio", default=time(8, 0))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "preferência de notificação"
        verbose_name_plural = "preferências de notificação"

    def __str__(self) -> str:
        return f"Preferências de {self.user.email}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        DUE_REMINDER = "due_reminder", "Lembrete de vencimento"
        RISK_ALERT = "risk_alert", "Alerta de risco"
        WEEKLY_SUMMARY = "weekly_summary", "Resumo semanal"
        SYSTEM = "system", "Sistema"

    class Channel(models.TextChoices):
        IN_APP = "in_app", "No aplicativo"
        EMAIL = "email", "E-mail"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviada"
        READ = "read", "Lida"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", verbose_name="usuário"
    )
    kind = models.CharField("tipo", max_length=32, choices=Kind.choices)
    title = models.CharField("título", max_length=120)
    body = models.CharField("corpo", max_length=500)
    channel = models.CharField(
        "canal", max_length=12, choices=Channel.choices, default=Channel.IN_APP
    )
    status = models.CharField(
        "status", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    scheduled_at = models.DateTimeField("agendada para", null=True, blank=True)
    sent_at = models.DateTimeField("enviada em", null=True, blank=True)
    read_at = models.DateTimeField("lida em", null=True, blank=True)
    payload = models.JSONField("payload", default=dict, blank=True)
    dedupe_key = models.CharField("chave de deduplicação", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["due_reminder", "risk_alert", "weekly_summary", "system"]),
                name="ck_notification_kind",
            ),
            models.CheckConstraint(
                condition=Q(channel__in=["in_app", "email"]), name="ck_notification_channel"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "sent", "read", "failed"]),
                name="ck_notification_status",
            ),
            models.UniqueConstraint(
                fields=["user", "dedupe_key"],
                condition=Q(dedupe_key__gt=""),
                name="uq_notification_user_dedupe",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["scheduled_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def mark_read(self):
        if self.status != self.Status.READ:
            self.status = self.Status.READ
            self.read_at = timezone.now()
            self.save(update_fields=["status", "read_at"])

    @property
    def is_unread(self) -> bool:
        return self.status != self.Status.READ
