from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import NotificationPreferenceForm
from .models import Notification
from .services import get_preferences


def _owned(request, pk):
    try:
        return get_object_or_404(Notification, pk=pk, user=request.user)
    except (ValidationError, Http404):
        raise Http404 from None


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "notifications/list.html", {"notifications": notifications})


@login_required
@require_POST
def mark_read(request, pk):
    notification = _owned(request, pk)
    notification.mark_read()
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user).exclude(status=Notification.Status.READ).update(
        status=Notification.Status.READ, read_at=timezone.now()
    )
    messages.success(request, "Notificações marcadas como lidas.")
    return redirect("notifications:list")


@login_required
def preferences(request):
    preference = get_preferences(request.user)
    form = NotificationPreferenceForm(request.POST or None, instance=preference)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Preferências de notificação atualizadas.")
        return redirect("notifications:preferences")
    return render(
        request,
        "notifications/preferences.html",
        {"form": form, "preference": preference},
    )
