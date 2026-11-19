from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.notifications.services import send_due_reminders


class Command(BaseCommand):
    help = "Cria e envia lembretes de vencimento (dívidas e plano)."

    def handle(self, *args, **options):
        count = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"{count} lembrete(s) criado(s)."))
