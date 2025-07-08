from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from Staff.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ("email", "name", "role", "is_staff", "is_superuser")
    search_fields = ("email", "name", "contact_phone")
    readonly_fields = ("last_login",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("name", "contact_phone", "role")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important Dates", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "name",
                    "contact_phone",
                    "role",
                ),
            },
        ),
    )

    search_fields = ("email", "name")
