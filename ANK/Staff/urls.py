from django.urls import path
from Staff.views import (
    UserList,
    UserDetail,
    UserGuestFieldAPIView,
    UserGuestFieldAddAPIView,
    UserGuestFieldRemoveAPIView,
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
    # ─── User ↔ GuestField assignment ──────────────────────────────────
    # GET list, PUT replace entire list
    path(
        "users/<uuid:pk>/guestfields/",
        UserGuestFieldAPIView.as_view(),
        name="user-guestfields",
    ),
    # POST add a single guestfield
    path(
        "users/<uuid:pk>/guestfields/add/",
        UserGuestFieldAddAPIView.as_view(),
        name="user-guestfields-add",
    ),
    # DELETE remove a single guestfield
    path(
        "users/<uuid:pk>/guestfields/<uuid:field_pk>/",
        UserGuestFieldRemoveAPIView.as_view(),
        name="user-guestfields-remove",
    ),
]
