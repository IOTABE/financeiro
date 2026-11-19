from __future__ import annotations

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "user", "entity_type", "entity_id")
    list_filter = ("event",)
    search_fields = ("user__email", "entity_id")
    readonly_fields = (
        "user",
        "event",
        "entity_type",
        "entity_id",
        "metadata",
        "ip_hash",
        "user_agent_hash",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
