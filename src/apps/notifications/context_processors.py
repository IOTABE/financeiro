from __future__ import annotations

from .services import unread_count


def notifications(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notifications": 0}
    try:
        return {"unread_notifications": unread_count(request.user)}
    except Exception:
        return {"unread_notifications": 0}
