from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.debts.models import Debt
from apps.finance.models import Account, Category, Transaction
from apps.finance.services import ensure_finance_setup
from apps.notifications.models import NotificationPreference
from apps.plans.services import generate_plan

User = get_user_model()


class Command(BaseCommand):
    help = "Cria um usuário de demonstração com dados, dívidas e plano."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@clareza.local")
        parser.add_argument("--password", default="DemoClareza123")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove o usuário existente e recria os dados.",
        )

    def handle(self, *args, **options):
        email = options["email"].lower()
        password = options["password"]
        if options["reset"]:
            User.objects.filter(email=email).delete()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": "Usuário Demonstração"},
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        ensure_finance_setup(user)

        profile = user.profile
        profile.gross_income = Decimal("5200.00")
        profile.net_income = Decimal("4200.00")
        profile.essential_expenses = Decimal("2600.00")
        profile.min_existential = Decimal("1800.00")
        profile.other_planned_expenses = Decimal("200.00")
        profile.dependents = 1
        profile.onboarding_completed_at = timezone.now()
        profile.save()

        NotificationPreference.objects.get_or_create(user=user)

        account = Account.objects.filter(user=user).first()
        salary_category = Category.objects.filter(
            user=user, kind=Category.Kind.INCOME, name="Salário"
        ).first()
        food_category = Category.objects.filter(
            user=user, kind=Category.Kind.EXPENSE, name="Alimentação"
        ).first()
        home_category = Category.objects.filter(
            user=user, kind=Category.Kind.EXPENSE, name="Moradia"
        ).first()

        today = timezone.localdate()
        if not Transaction.objects.filter(user=user).exists():
            Transaction.objects.create(
                user=user,
                account=account,
                category=salary_category,
                kind=Transaction.Kind.INCOME,
                amount=Decimal("4200.00"),
                description="Salário",
                transaction_date=today - timedelta(days=14),
                competence_month=today.replace(day=1),
                status=Transaction.Status.PAID,
                paid_at=today - timedelta(days=14),
            )
            Transaction.objects.create(
                user=user,
                account=account,
                category=home_category,
                kind=Transaction.Kind.EXPENSE,
                amount=Decimal("1800.00"),
                description="Aluguel",
                transaction_date=today - timedelta(days=10),
                competence_month=today.replace(day=1),
                status=Transaction.Status.PAID,
                paid_at=today - timedelta(days=10),
            )
            Transaction.objects.create(
                user=user,
                account=account,
                category=food_category,
                kind=Transaction.Kind.EXPENSE,
                amount=Decimal("650.00"),
                description="Supermercado",
                transaction_date=today - timedelta(days=2),
                competence_month=today.replace(day=1),
                status=Transaction.Status.PAID,
                paid_at=today - timedelta(days=2),
            )

        if not Debt.objects.filter(user=user, deleted_at__isnull=True).exists():
            for creditor, balance, rate, minimum, due_day in (
                ("Cartão principal", "6000.00", "0.0199", "300.00", 10),
                ("Empréstimo pessoal", "4000.00", "0.0125", "250.00", 5),
                ("Parcelado", "2000.00", "0.0099", "200.00", 15),
            ):
                Debt.objects.create(
                    user=user,
                    creditor=creditor,
                    nickname=creditor,
                    type=Debt.Type.CREDIT_CARD,
                    current_balance=Decimal(balance),
                    monthly_rate=Decimal(rate),
                    minimum_payment=Decimal(minimum),
                    due_day=due_day,
                    status=Debt.Status.ACTIVE,
                )

        plan = generate_plan(
            user,
            strategy="hybrid",
            start_month=date(today.year, today.month, 1),
            label="Plano demo",
        )
        from apps.plans.services import mark_schedule_paid

        first_due = plan.schedule.filter(payment__gt=0).order_by("competence_month", "id").first()
        if first_due and not first_due.is_paid:
            mark_schedule_paid(user=user, schedule=first_due)

        self.stdout.write(self.style.SUCCESS("Usuário de demonstração pronto."))
        self.stdout.write(f"E-mail: {email}")
        self.stdout.write(f"Senha: {password}")
        self.stdout.write(f"Plano: {plan.pk} ({plan.get_status_display()})")
