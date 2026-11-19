from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from apps.core.dates import add_months, due_date_in_month, month_start
from apps.debts.models import Debt
from apps.plans.services import current_plan

from .models import Notification, NotificationPreference

User = get_user_model()
ZERO = 0


def get_preferences(user) -> NotificationPreference:
    preferences, _ = NotificationPreference.objects.get_or_create(user=user)
    return preferences


def _next_due(due_day: int, today: date) -> date:
    candidate = due_date_in_month(today.year, today.month, due_day)
    if candidate < today:
        candidate = add_months(candidate, 1)
    return candidate


def upcoming_debts(user, days: int = 3, today: date | None = None) -> list[dict]:
    today = today or timezone.localdate()
    limit = today + timedelta(days=days)
    items = []
    for debt in Debt.objects.filter(
        user=user,
        status__in=[Debt.Status.ACTIVE, Debt.Status.LATE],
        deleted_at__isnull=True,
    ):
        due = _next_due(debt.due_day, today)
        if today <= due <= limit:
            items.append(
                {
                    "debt": debt,
                    "due_date": due,
                    "dedupe": f"debt-due:{debt.pk}:{due.isoformat()}",
                    "url": f"/dividas/{debt.pk}/",
                }
            )
    return items


def upcoming_plan_payments(user, days: int = 3, today: date | None = None) -> list[dict]:
    today = today or timezone.localdate()
    limit = today + timedelta(days=days)
    plan = current_plan(user)
    if not plan:
        return []
    items = []
    rows = plan.schedule.filter(payment__gt=0).select_related("debt", "adherence")
    for row in rows:
        if row.is_paid:
            continue
        due_day = row.debt.due_day if row.debt else 1
        due = due_date_in_month(row.competence_month.year, row.competence_month.month, due_day)
        if row.competence_month == month_start(today) and due < today:
            due = today
        if today <= due <= limit:
            items.append(
                {
                    "schedule": row,
                    "due_date": due,
                    "dedupe": f"plan-due:{row.pk}:{row.competence_month.isoformat()}",
                    "url": f"/plano/{plan.pk}/",
                }
            )
    return items


def _in_quiet_hours(preferences: NotificationPreference, now: datetime) -> bool:
    current = now.time()
    start = preferences.quiet_hours_start
    end = preferences.quiet_hours_end
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def create_notification(
    *,
    user,
    kind: str,
    title: str,
    body: str,
    dedupe_key: str,
    url: str = "",
) -> tuple[Notification, bool]:
    return Notification.objects.get_or_create(
        user=user,
        dedupe_key=dedupe_key,
        defaults={
            "kind": kind,
            "title": title,
            "body": body,
            "channel": Notification.Channel.IN_APP,
            "status": Notification.Status.SENT,
            "payload": {"url": url} if url else {},
        },
    )


def send_due_reminders_for_user(user, today: date | None = None) -> int:
    preferences = get_preferences(user)
    if not preferences.due_reminders:
        return 0
    today = today or timezone.localdate()
    now = timezone.now()
    count = 0
    items = upcoming_debts(user, today=today) + upcoming_plan_payments(user, today=today)
    for item in items:
        title = "Pagamento próximo"
        body = f"Você tem um pagamento previsto para {item['due_date']:%d/%m}. Abra o app para ver os detalhes."
        notification, created = create_notification(
            user=user,
            kind=Notification.Kind.DUE_REMINDER,
            title=title,
            body=body,
            dedupe_key=item["dedupe"],
            url=item["url"],
        )
        if not created:
            continue
        count += 1
        if preferences.email_enabled and not _in_quiet_hours(preferences, now):
            try:
                send_mail(
                    subject=title,
                    message=body,
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                notification.sent_at = timezone.now()
                notification.save(update_fields=["sent_at"])
            except Exception:
                notification.status = Notification.Status.FAILED
                notification.save(update_fields=["status"])
    return count


def send_due_reminders(today: date | None = None) -> int:
    total = 0
    for user in User.objects.filter(is_active=True).iterator():
        total += send_due_reminders_for_user(user, today=today)
    return total


def unread_count(user) -> int:
    return Notification.objects.filter(user=user).exclude(status=Notification.Status.READ).count()
