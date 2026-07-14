from rest_framework.permissions import BasePermission


class IsWhatsAppAdmin(BasePermission):
    message = "WhatsApp reconciliation requires an admin or super admin account."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) in {"admin", "super_admin"}
        )
