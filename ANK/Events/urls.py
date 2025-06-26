from django.urls import path
from Events.views.event_views import (
    EventListCreateView,
    EventDetailView,
    EventRegistrationListCreateView,
    EventRegistrationDetailView,
)
from Events.views.session_views import (
    SessionListCreateView,
    SessionDetailView,
    SessionRegistrationListCreateView,
    SessionRegistrationDetailView,
)

urlpatterns = [
    # ─── Event CRUD ───────────────────────────────────────────────────────
    path(
        "events/",
        EventListCreateView.as_view(),
        name="event-list",  # GET list, POST create
    ),
    path(
        "events/create/",
        EventListCreateView.as_view(),
        name="event-create",  # alias for POST create
    ),
    path(
        "events/<uuid:pk>/",
        EventDetailView.as_view(),
        name="event-detail",  # GET retrieve
    ),
    path(
        "events/<uuid:pk>/update/",
        EventDetailView.as_view(),
        name="event-update",  # PUT update
    ),
    path(
        "events/<uuid:pk>/delete/",
        EventDetailView.as_view(),
        name="event-delete",  # DELETE delete
    ),
    # ─── EventRegistration CRUD ───────────────────────────────────────────
    path(
        "event-registrations/",
        EventRegistrationListCreateView.as_view(),
        name="eventregistration-list",  # GET list, POST create
    ),
    path(
        "event-registrations/create/",
        EventRegistrationListCreateView.as_view(),
        name="eventregistration-create",  # alias for POST create
    ),
    path(
        "event-registrations/<uuid:pk>/",
        EventRegistrationDetailView.as_view(),
        name="eventregistration-detail",  # GET retrieve
    ),
    path(
        "event-registrations/<uuid:pk>/update/",
        EventRegistrationDetailView.as_view(),
        name="eventregistration-update",  # PUT update
    ),
    path(
        "event-registrations/<uuid:pk>/delete/",
        EventRegistrationDetailView.as_view(),
        name="eventregistration-delete",  # DELETE delete
    ),
    # ─── Session CRUD ────────────────────────────────────────────────────
    path(
        "sessions/",
        SessionListCreateView.as_view(),
        name="session-list",  # GET list, POST create
    ),
    path(
        "sessions/create/",
        SessionListCreateView.as_view(),
        name="session-create",  # alias for POST create
    ),
    path(
        "sessions/<uuid:pk>/",
        SessionDetailView.as_view(),
        name="session-detail",  # GET retrieve
    ),
    path(
        "sessions/<uuid:pk>/update/",
        SessionDetailView.as_view(),
        name="session-update",  # PUT update
    ),
    path(
        "sessions/<uuid:pk>/delete/",
        SessionDetailView.as_view(),
        name="session-delete",  # DELETE delete
    ),
    # ─── SessionRegistration CRUD ────────────────────────────────────────
    path(
        "session-registrations/",
        SessionRegistrationListCreateView.as_view(),
        name="sessionregistration-list",  # GET list, POST create
    ),
    path(
        "session-registrations/create/",
        SessionRegistrationListCreateView.as_view(),
        name="sessionregistration-create",  # alias for POST create
    ),
    path(
        "session-registrations/<uuid:pk>/",
        SessionRegistrationDetailView.as_view(),
        name="sessionregistration-detail",  # GET retrieve
    ),
    path(
        "session-registrations/<uuid:pk>/update/",
        SessionRegistrationDetailView.as_view(),
        name="sessionregistration-update",  # PUT update
    ),
    path(
        "session-registrations/<uuid:pk>/delete/",
        SessionRegistrationDetailView.as_view(),
        name="sessionregistration-delete",  # DELETE delete
    ),
]
