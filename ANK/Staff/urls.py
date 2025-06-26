from django.urls import path
from Staff.views import (
    UserList,
    UserDetail,
    UserGuestFieldAPIView,
    RegisterView,
    LoginView,
    RefreshView,
    LogoutView,
)

urlpatterns = [
    # ─── Authentication endpoints ──────────────────────────────────────
    # Register a new user
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    # → Obtain tokens
    path("auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    # → Refresh access token
    path("auth/refresh/", RefreshView.as_view(), name="token_refresh"),
    # → “Logout” by blacklisting the refresh token
    path("auth/logout/", LogoutView.as_view(), name="token_logout"),
    # ─── User endpoints ──────────────────────────────────────────────────
    path("users/", UserList.as_view(), name="user-list"),  # GET list
    path("users/create/", UserList.as_view(), name="user-create"),  # POST create
    path("users/<uuid:pk>/", UserDetail.as_view(), name="user-detail"),  # GET retrieve
    path(
        "users/<uuid:pk>/update/", UserDetail.as_view(), name="user-update"
    ),  # PUT update
    path(
        "users/<uuid:pk>/delete/", UserDetail.as_view(), name="user-delete"
    ),  # DELETE delete
    # ─── User ↔ GuestField assignment ────────────────────────────────────
    path(
        "users/<uuid:pk>/guestfields/",
        UserGuestFieldAPIView.as_view(),
        name="user-guestfields-list",
    ),  # GET current list
    path(
        "users/<uuid:pk>/guestfields/update/",
        UserGuestFieldAPIView.as_view(),
        name="user-guestfields-update",
    ),  # POST replace list
]
