"""
URL configuration for ANK project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from Events.views.webhooks import (
    message_logs,
    message_logs_latest,
    message_status_lookup,
    message_status_webhook,
    resolve_wa,
    track_send,
    whatsapp_rsvp,
)
from MessageTemplates.whatsapp_views.travel_detail_view import whatsapp_travel_webhook

from ANK.csrf import csrf


def healthz(_):
    return HttpResponse("ok", content_type="text/plain")


def root(_request):
    return JsonResponse({"ok": True, "service": "ank-backend"})


urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/", include("Staff.urls")),
    path("api/csrf/", csrf),
    path("api/", include("Events.urls")),
    path("api/", include("Guest.urls")),
    path("api/", include("Logistics.urls")),
    path("api/", include("MessageTemplates.urls")),
    path("api/", include("Departments.urls")),
    path("api/", include("utilities.urls")),
    path("api/", include("CustomField.urls")),
    path("api/manpower/", include("Manpower.urls")),
    # API schema generation (raw OpenAPI)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Redoc UI
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # ----------------- Webhook -------------------- #
    path("api/webhooks/whatsapp-rsvp/", whatsapp_rsvp, name="whatsapp_rsvp"),
    # path("api/debug/echo-secret/", echo_secret),
    path("api/webhooks/track-send/", track_send, name="track_send"),
    path("api/webhooks/whatsapp-travel/", whatsapp_travel_webhook),
    path(
        "api/webhooks/message-status/",
        message_status_webhook,
        name="message_status_webhook",
    ),
    path(
        "api/webhooks/message-status-lookup/",
        message_status_lookup,
        name="message_status_lookup",
    ),
    path(
        "api/webhooks/message-logs/",
        message_logs,
        name="message_logs",
    ),
    path(
        "api/webhooks/message-logs/latest/",
        message_logs_latest,
        name="message_logs_latest",
    ),
    path("healthz", healthz),
    path("api/internal/resolve-wa/<str:wa_id>/", resolve_wa, name="resolve_wa"),
]
