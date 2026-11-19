from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.finance.services import materialize_user_recurrences


class Command(BaseCommand):
    help = "Materializa transações de recorrências ativas até a data atual."

    def handle(self, *args, **options):
        total = 0
        for user in get_user_model().objects.filter(is_active=True).iterator():
            total += materialize_user_recurrences(user)
        self.stdout.write(self.style.SUCCESS(f"{total} transação(ões) criada(s)."))
