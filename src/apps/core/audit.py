from __future__ import annotations

import hashlib

from .models import AuditLog


def _hash(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_event(
    *,
    event: str,
    user=None,
    request=None,
    entity_type: str = "",
    entity_id: str = "",
    metadata: dict | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        user=user,
        event=event,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else "",
        metadata=metadata or {},
        ip_hash=_hash(client_ip(request)) if request else "",
        user_agent_hash=_hash(request.META.get("HTTP_USER_AGENT", "")) if request else "",
    )
