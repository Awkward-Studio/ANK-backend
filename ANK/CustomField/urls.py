from django.urls import path

from CustomField.views import (
    AccommodationCustomFieldValueDetailView,
    AccommodationCustomFieldValueView,
    CustomFieldDefinitionDetailView,
    CustomFieldDefinitionListCreateView,
    EventCustomFieldValueDetailView,
    EventCustomFieldValueView,
    EventCustomFieldValuesListView,
    EventRegistrationCustomFieldValueDetailView,
    EventRegistrationCustomFieldValueView,
    SessionCustomFieldValueDetailView,
    SessionCustomFieldValueView,
    TravelDetailCustomFieldValueDetailView,
    TravelDetailCustomFieldValueView,
)

urlpatterns = [
    # Custom Field Definitions
    path(
        "custom-fields/definitions/",
        CustomFieldDefinitionListCreateView.as_view(),
        name="custom-field-definitions-list",
    ),
    path(
        "custom-fields/definitions/<uuid:pk>/",
        CustomFieldDefinitionDetailView.as_view(),
        name="custom-field-definition-detail",
    ),
    # Event Registration Custom Field Values
    path(
        "event-registrations/<uuid:registration_id>/custom-fields/",
        EventRegistrationCustomFieldValueView.as_view(),
        name="event-registration-custom-fields",
    ),
    path(
        "event-registrations/<uuid:registration_id>/custom-fields/<str:field_name>/",
        EventRegistrationCustomFieldValueDetailView.as_view(),
        name="event-registration-custom-field-detail",
    ),
    # Event-level: Get all registrations with custom fields
    path(
        "events/<uuid:event_id>/registrations/custom-fields/",
        EventCustomFieldValuesListView.as_view(),
        name="event-registrations-custom-fields-list",
    ),
    # Session Custom Field Values
    path(
        "sessions/<uuid:session_id>/custom-fields/",
        SessionCustomFieldValueView.as_view(),
        name="session-custom-fields",
    ),
    path(
        "sessions/<uuid:session_id>/custom-fields/<str:field_name>/",
        SessionCustomFieldValueDetailView.as_view(),
        name="session-custom-field-detail",
    ),
    # Accommodation Custom Field Values
    path(
        "accommodations/<uuid:accommodation_id>/custom-fields/",
        AccommodationCustomFieldValueView.as_view(),
        name="accommodation-custom-fields",
    ),
    path(
        "accommodations/<uuid:accommodation_id>/custom-fields/<str:field_name>/",
        AccommodationCustomFieldValueDetailView.as_view(),
        name="accommodation-custom-field-detail",
    ),
    # TravelDetail Custom Field Values
    path(
        "traveldetails/<uuid:traveldetail_id>/custom-fields/",
        TravelDetailCustomFieldValueView.as_view(),
        name="traveldetail-custom-fields",
    ),
    path(
        "traveldetails/<uuid:traveldetail_id>/custom-fields/<str:field_name>/",
        TravelDetailCustomFieldValueDetailView.as_view(),
        name="traveldetail-custom-field-detail",
    ),
    # Event Custom Field Values
    path(
        "events/<uuid:event_id>/custom-fields/",
        EventCustomFieldValueView.as_view(),
        name="event-custom-fields",
    ),
    path(
        "events/<uuid:event_id>/custom-fields/<str:field_name>/",
        EventCustomFieldValueDetailView.as_view(),
        name="event-custom-field-detail",
    ),
]
