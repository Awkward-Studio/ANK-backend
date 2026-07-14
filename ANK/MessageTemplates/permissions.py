import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsWhatsAppAdminOrInternalService(BasePermission):
    """Authorize WhatsApp administrators or the trusted Next.js service.

    The internal-secret branch preserves server-to-server compatibility while
    browser-driven management requests use Django JWT authentication.
    """

    message = "WhatsApp administration requires an admin or super admin account."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "role", None) in {
            "admin",
            "super_admin",
        }:
            return True

        provided = request.headers.get("X-Internal-Service-Token", "") or request.headers.get(
            "X-Webhook-Token", ""
        )
        if not provided:
            return False

        candidates = {
            getattr(settings, "ANK_INTERNAL_API_SECRET", ""),
            getattr(settings, "ANK_INTERNAL_API_SECRET_PREVIOUS", ""),
        }
        return any(
            candidate and hmac.compare_digest(provided, candidate)
            for candidate in candidates
        )


class IsAuthenticatedOrInternalService(IsWhatsAppAdminOrInternalService):
    """Allow authenticated application workflows to read sender metadata."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return True
        return super().has_permission(request, view)
