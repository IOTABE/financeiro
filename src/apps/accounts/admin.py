from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import Consent, Profile, User


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = AdminUserCreationForm
    ordering = ("email",)
    list_display = ("email", "full_name", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Pessoal", {"fields": ("full_name",)}),
        (
            "Permissões",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "net_income", "essential_expenses", "updated_at")
    search_fields = ("user__email", "user__full_name")


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "version", "accepted", "accepted_at")
    list_filter = ("kind", "version", "accepted")
    search_fields = ("user__email",)
    readonly_fields = ("accepted_at", "ip_hash", "user_agent_hash")
