from django.urls import path
from Staff.google_calendar import (
    google_calendar_callback,
    google_calendar_complete,
    google_calendar_connection,
    google_calendar_event,
    google_calendar_events,
    google_calendar_start,
)
from Staff.views import (
    UserAssignedEventsAPIView,
    UserAssignedSessionsAPIView,
    UserList,
    UserDetail,
    RegisterView,
    LoginView,
    RefreshView,
    LogoutView,
)

urlpatterns = [
    # ─── Authentication endpoints ──────────────────────────────────────
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="token_logout"),
    path(
        "auth/google/calendar/callback/",
        google_calendar_callback,
        name="google-calendar-callback",
    ),
    path("team-calendar/connection/", google_calendar_connection),
    path("team-calendar/connect/", google_calendar_start),
    path("team-calendar/connect/complete/", google_calendar_complete),
    path("team-calendar/events/", google_calendar_events),
    path("team-calendar/events/<str:event_id>/", google_calendar_event),
    # ─── User CRUD ────────────────────────────────────────────────────
    # GET list, POST create
    path("users/", UserList.as_view(), name="user-list"),
    # GET retrieve, PUT update, DELETE destroy
    path("users/<uuid:pk>/", UserDetail.as_view(), name="user-detail"),
    # Fetch event and sessions for a user
    path(
        "users/<uuid:pk>/assigned-events/",
        UserAssignedEventsAPIView.as_view(),
        name="user-assigned-events",
    ),
    path(
        "users/<uuid:pk>/assigned-sessions/",
        UserAssignedSessionsAPIView.as_view(),
        name="user-assigned-sessions",
    ),
]
