from django.urls import path
from Events.views.event_views import (
    EventAccommodationsAPIView,
    EventListCreateView,
    EventDetailView,
    EventRegistrationAccommodationsAPIView,
    EventRegistrationAttendeesAPIView,
    EventRegistrationListCreateView,
    EventRegistrationDetailView,
    EventRegistrationTravelDetailsAPIView,
    EventRegistrationsAPIView,
    EventSessionsAPIView,
    EventTravelDetailsAPIView,
    ExtraAttendeeAccommodationsAPIView,
    ExtraAttendeeListCreateView,
    ExtraAttendeeDetailView,
    EventFieldList,
    EventFieldDetail,
    EventAllAttendeesAPIView,
    ExtraAttendeeTravelDetailsAPIView,
    ExtraAttendeesForRegistrationAPIView,
)
from Events.views.session_views import (
    SessionListCreateView,
    SessionDetailView,
    SessionRegistrationAttendeesAPIView,
    SessionRegistrationListCreateView,
    SessionRegistrationDetailView,
    SessionFieldList,
    SessionFieldDetail,
    SessionRegistrationsAPIView,
)
from Events.views.staff_assignment_views import (
    EventStaffAssignmentList,
    EventStaffAssignmentDetail,
    SessionStaffAssignmentList,
    SessionStaffAssignmentDetail,
)
from Events.views.staff_event_fields_permissions_views import (
    UserEventEventFieldPermsAPIView,
    UserEventEventFieldPermAddRemoveAPIView,
    UserEventGuestFieldPermsAPIView,
    UserEventGuestFieldPermAddRemoveAPIView,
    UserEventSessionFieldPermsAPIView,
    UserEventSessionFieldPermAddRemoveAPIView,
)

urlpatterns = [
    # ─── Events ────────────────────────────────────────────────────────────
    path("events/", EventListCreateView.as_view(), name="event-list"),
    path("events/<uuid:pk>/", EventDetailView.as_view(), name="event-detail"),
    path(
        "events/<uuid:pk>/sessions/",
        EventSessionsAPIView.as_view(),
        name="event-sessions",
    ),
    path(
        "events/<uuid:pk>/registrations/",
        EventRegistrationsAPIView.as_view(),
        name="event-registrations",
    ),
    path(
        "events/<uuid:pk>/accommodations/",
        EventAccommodationsAPIView.as_view(),
        name="event-accommodations",
    ),
    path(
        "events/<uuid:pk>/traveldetails/",
        EventTravelDetailsAPIView.as_view(),
        name="event-traveldetails",
    ),
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
    #
    path(
        "event-registrations/<uuid:pk>/extra-attendees/",
        ExtraAttendeesForRegistrationAPIView.as_view(),
        name="eventregistration-extraattendees",
    ),
    path(
        "event-registrations/<uuid:pk>/accommodations/",
        EventRegistrationAccommodationsAPIView.as_view(),
        name="eventregistration-accommodations",
    ),
    path(
        "event-registrations/<uuid:pk>/traveldetails/",
        EventRegistrationTravelDetailsAPIView.as_view(),
        name="eventregistration-traveldetails",
    ),
    path(
        "event-registrations/<uuid:registration_pk>/attendees/",
        EventRegistrationAttendeesAPIView.as_view(),
        name="eventregistration-attendees",
    ),
    # ─── Sessions ─────────────────────────────────────────────────────────
    path("sessions/", SessionListCreateView.as_view(), name="session-list"),
    path("sessions/<uuid:pk>/", SessionDetailView.as_view(), name="session-detail"),
    path(
        "sessions/<uuid:pk>/registrations/",
        SessionRegistrationsAPIView.as_view(),
        name="session-registrations",
    ),
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
    path(
        "session-registrations/<uuid:registration_pk>/attendees/",
        SessionRegistrationAttendeesAPIView.as_view(),
        name="sessionregistration-attendees",
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
    path(
        "extra-attendees/<uuid:pk>/accommodations/",
        ExtraAttendeeAccommodationsAPIView.as_view(),
        name="extraattendee-accommodations",
    ),
    path(
        "extra-attendees/<uuid:pk>/traveldetails/",
        ExtraAttendeeTravelDetailsAPIView.as_view(),
        name="extraattendee-traveldetails",
    ),
    # EventField CRUD
    path("event-fields/", EventFieldList.as_view(), name="eventfield-list"),
    path(
        "event-fields/<uuid:pk>/", EventFieldDetail.as_view(), name="eventfield-detail"
    ),
    path("session-fields/", SessionFieldList.as_view(), name="sessionfield-list"),
    path(
        "session-fields/<uuid:pk>/",
        SessionFieldDetail.as_view(),
        name="sessionfield-detail",
    ),
    # EventField perms for user on event
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/eventfields/",
        UserEventEventFieldPermsAPIView.as_view(),
        name="user-eventfields-list",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/eventfields/add/",
        UserEventEventFieldPermAddRemoveAPIView.as_view(),
        name="user-eventfields-add",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/eventfields/<uuid:field_pk>/",
        UserEventEventFieldPermAddRemoveAPIView.as_view(),
        name="user-eventfields-remove",
    ),
    # GuestField perms for user on event
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/guestfields/",
        UserEventGuestFieldPermsAPIView.as_view(),
        name="user-guestfields-list",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/guestfields/add/",
        UserEventGuestFieldPermAddRemoveAPIView.as_view(),
        name="user-guestfields-add",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/guestfields/<uuid:field_pk>/",
        UserEventGuestFieldPermAddRemoveAPIView.as_view(),
        name="user-guestfields-remove",
    ),
    # SessionField perms for user on event
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/sessionfields/",
        UserEventSessionFieldPermsAPIView.as_view(),
        name="user-sessionfields-list",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/sessionfields/add/",
        UserEventSessionFieldPermAddRemoveAPIView.as_view(),
        name="user-sessionfields-add",
    ),
    path(
        "events/<uuid:event_pk>/users/<uuid:user_pk>/sessionfields/<uuid:field_pk>/",
        UserEventSessionFieldPermAddRemoveAPIView.as_view(),
        name="user-sessionfields-remove",
    ),
    # Fetch all guest(and their extra-attendees) for an event.
    path(
        "events/<uuid:event_pk>/all-attendees/",
        EventAllAttendeesAPIView.as_view(),
        name="event-all-attendees",
    ),
]
