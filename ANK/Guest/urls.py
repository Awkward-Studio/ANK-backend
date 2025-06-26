from django.urls import path
from Guest.views import (
    GuestFieldList,
    GuestFieldDetail,
    GuestList,
    GuestDetail,
)

urlpatterns = [
    # ─── GuestField endpoints ────────────────────────────────────────────
    path("guestfields/", GuestFieldList.as_view(), name="guestfield-list"),  # GET list
    path(
        "guestfields/create/", GuestFieldList.as_view(), name="guestfield-create"
    ),  # POST create
    path(
        "guestfields/<int:pk>/", GuestFieldDetail.as_view(), name="guestfield-detail"
    ),  # GET retrieve
    path(
        "guestfields/<int:pk>/update/",
        GuestFieldDetail.as_view(),
        name="guestfield-update",
    ),  # PUT update
    path(
        "guestfields/<int:pk>/delete/",
        GuestFieldDetail.as_view(),
        name="guestfield-delete",
    ),  # DELETE delete
    # ─── Guest endpoints ─────────────────────────────────────────────────
    path("guests/", GuestList.as_view(), name="guest-list"),  # GET list
    path("guests/create/", GuestList.as_view(), name="guest-create"),  # POST create
    path(
        "guests/<uuid:pk>/", GuestDetail.as_view(), name="guest-detail"
    ),  # GET retrieve
    path(
        "guests/<uuid:pk>/update/", GuestDetail.as_view(), name="guest-update"
    ),  # PUT update
    path(
        "guests/<uuid:pk>/delete/", GuestDetail.as_view(), name="guest-delete"
    ),  # DELETE delete
]
