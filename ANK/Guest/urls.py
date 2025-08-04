from django.urls import path
from Guest.views import (
    GuestFieldList,
    GuestFieldDetail,
    GuestList,
    GuestDetail,
    BulkGuestUploadAPIView,
)

urlpatterns = [
    # ─── GuestField ─────────────────────────────────────────────────
    # GET  list,  POST create
    path("guest-fields/", GuestFieldList.as_view(), name="guestfield-list"),
    # GET retrieve, PUT update, DELETE destroy
    path(
        "guest-fields/<uuid:pk>/", GuestFieldDetail.as_view(), name="guestfield-detail"
    ),
    # ─── Guest ───────────────────────────────────────────────────────
    # GET  list,  POST create
    path("guests/", GuestList.as_view(), name="guest-list"),
    # GET retrieve, PUT update, DELETE destroy
    path("guests/<uuid:pk>/", GuestDetail.as_view(), name="guest-detail"),
    path(
        "guest-list/<uuid:event_id>/upload-guests-csv/",
        BulkGuestUploadAPIView.as_view(),
        name="event-upload-guests-csv",
    ),
]
