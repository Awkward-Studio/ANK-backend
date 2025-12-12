from django.urls import path

from CustomField.views import (
    CustomFieldDefinitionDetailView,
    CustomFieldDefinitionListCreateView,
    EventCustomFieldValuesListView,
    EventRegistrationCustomFieldValueDetailView,
    EventRegistrationCustomFieldValueView,
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
]
