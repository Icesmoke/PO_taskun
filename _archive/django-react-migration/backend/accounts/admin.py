from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "worker_role", "enabled", "is_staff")
    list_filter = ("enabled", "is_staff", "worker_role")
    search_fields = ("username", "full_name")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Профиль", {"fields": ("full_name", "worker_role", "tarif_per_hour", "enabled")}),
        ("Legacy", {"fields": ("legacy_password_hash",), "classes": ("collapse",)}),
        (
            "Права",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "full_name", "worker_role"),
            },
        ),
    )
