from django.urls import path
from Events.views.event_views import (
    EventListCreateView,
    EventDetailView,
    EventRegistrationListCreateView,
    EventRegistrationDetailView,
    ExtraAttendeeListCreateView,
    ExtraAttendeeDetailView,
)
from Events.views.session_views import (
    SessionListCreateView,
    SessionDetailView,
    SessionRegistrationListCreateView,
    SessionRegistrationDetailView,
)
from Events.views.staff_assignment_views import (
    EventStaffAssignmentList,
    EventStaffAssignmentDetail,
    SessionStaffAssignmentList,
    SessionStaffAssignmentDetail,
)

urlpatterns = [
    # ─── Events ────────────────────────────────────────────────────────────
    path("events/", EventListCreateView.as_view(), name="event-list"),
    path("events/<uuid:pk>/", EventDetailView.as_view(), name="event-detail"),
    # ─── Event Registrations ───────────────────────────────────────────────
    path(
        "event-registrations/",
        EventRegistrationListCreateView.as_view(),
        name="eventregistration-list",
    ),
    path(
        "event-registrations/<uuid:pk>/",
        EventRegistrationDetailView.as_view(),
        name="eventregistration-detail",
    ),
    # ─── Sessions ─────────────────────────────────────────────────────────
    path("sessions/", SessionListCreateView.as_view(), name="session-list"),
    path("sessions/<uuid:pk>/", SessionDetailView.as_view(), name="session-detail"),
    # ─── Session Registrations ────────────────────────────────────────────
    path(
        "session-registrations/",
        SessionRegistrationListCreateView.as_view(),
        name="sessionregistration-list",
    ),
    path(
        "session-registrations/<uuid:pk>/",
        SessionRegistrationDetailView.as_view(),
        name="sessionregistration-detail",
    ),
    # ─── Event Staff Assignments ──────────────────────────────────────────
    path(
        "assignments/event-staff/",
        EventStaffAssignmentList.as_view(),
        name="eventstaffassignment-list",
    ),
    path(
        "assignments/event-staff/<uuid:pk>/",
        EventStaffAssignmentDetail.as_view(),
        name="eventstaffassignment-detail",
    ),
    # ─── Session Staff Assignments ────────────────────────────────────────
    path(
        "assignments/session-staff/",
        SessionStaffAssignmentList.as_view(),
        name="sessionstaffassignment-list",
    ),
    path(
        "assignments/session-staff/<uuid:pk>/",
        SessionStaffAssignmentDetail.as_view(),
        name="sessionstaffassignment-detail",
    ),
    # ─── Extra Attendees ──────────────────────────────────────────────────
    path(
        "extra-attendees/",
        ExtraAttendeeListCreateView.as_view(),
        name="extraattendee-list",
    ),
    path(
        "extra-attendees/<uuid:pk>/",
        ExtraAttendeeDetailView.as_view(),
        name="extraattendee-detail",
    ),
]
