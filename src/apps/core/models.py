from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="usuário",
    )
    event = models.CharField("evento", max_length=64)
    entity_type = models.CharField("tipo de entidade", max_length=48, blank=True)
    entity_id = models.CharField("id da entidade", max_length=64, blank=True)
    metadata = models.JSONField("metadados", default=dict, blank=True)
    ip_hash = models.CharField("hash do IP", max_length=64, blank=True)
    user_agent_hash = models.CharField("hash do user-agent", max_length=64, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "log de auditoria"
        verbose_name_plural = "logs de auditoria"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%d/%m/%Y %H:%M} · {self.event}"
