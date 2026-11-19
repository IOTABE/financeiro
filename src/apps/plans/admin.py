from __future__ import annotations

from django.contrib import admin

from .models import Plan, PlanItem, PlanPayment, PlanSchedule, Simulation


class PlanItemInline(admin.TabularInline):
    model = PlanItem
    extra = 0
    readonly_fields = ("debt_name", "priority_order", "reason")


class PlanScheduleInline(admin.TabularInline):
    model = PlanSchedule
    extra = 0
    fields = (
        "competence_month",
        "debt_name",
        "payment",
        "interest",
        "principal",
        "closing_balance",
    )
    readonly_fields = fields
    can_delete = False
    max_num = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("user", "strategy", "status", "months_to_payoff", "generated_at")
    list_filter = ("strategy", "status")
    search_fields = ("user__email", "label")
    inlines = [PlanItemInline, PlanScheduleInline]
    readonly_fields = ("input_snapshot", "summary")


@admin.register(PlanPayment)
class PlanPaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "schedule", "amount", "paid_at")
    list_filter = ("paid_at",)
    search_fields = ("user__email",)


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "kind", "created_at", "applied_at")
    list_filter = ("kind",)
    search_fields = ("user__email", "name")
    readonly_fields = ("params", "result_summary")
