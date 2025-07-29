from django.urls import path
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
