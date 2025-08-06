from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class DevCsrfBypassMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Only bypass if request is from localhost:3000 and in DEBUG mode
        origin = request.META.get("HTTP_ORIGIN")
        if settings.DEBUG and origin == "http://localhost:3000":
            setattr(request, "_dont_enforce_csrf_checks", True)
