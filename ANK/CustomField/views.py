from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404
from Events.models.event_registration_model import EventRegistration
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from CustomField.models import CustomFieldDefinition, CustomFieldValue
from CustomField.serializers import (
    BulkCustomFieldValueSerializer,
    CustomFieldDefinitionSerializer,
    CustomFieldValueSerializer,
    EventRegistrationWithCustomFieldsSerializer,
)
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=CustomFieldDefinitionSerializer(many=True),
            parameters=[
                query_param("event_id", "uuid", True, "Event UUID (required)"),
                query_param("model", "str", False, "Filter by model: eventregistration, session, accommodation, traveldetail, sessionregistration, event"),
            ],
            description="List all custom field definitions for an event",
            tags=["Custom Fields"],
        ),
        "post": doc_create(
            request=CustomFieldDefinitionSerializer,
            response=CustomFieldDefinitionSerializer,
            description="Create a new custom field definition for an event",
            tags=["Custom Fields"],
        ),
    }
)
class CustomFieldDefinitionListCreateView(APIView):
    """
    GET: List all custom field definitions for an event (optionally filter by model)
    POST: Create a new custom field definition

    Query Params:
    - event_id: REQUIRED - UUID of the event
    - model: Optional - Filter by model name (e.g., 'eventregistration', 'event', 'session')
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all custom field definitions for an event"""
        event_id = request.query_params.get("event_id", None)

        # Require event_id
        if not event_id:
            return Response(
                {"error": "event_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify event exists
        from Events.models.event_model import Event
        event = get_object_or_404(Event, pk=event_id)

        # Filter by event
        queryset = CustomFieldDefinition.objects.filter(event=event)

        model_filter = request.query_params.get("model", None)

        if model_filter:
            try:
                # Map model names to app labels
                model_map = {
                    "eventregistration": ("Events", "eventregistration"),
                    "sessionregistration": ("Events", "sessionregistration"),
                    "accommodation": ("Logistics", "accommodation"),
                    "traveldetail": ("Logistics", "traveldetail"),
                    "session": ("Events", "session"),
                    "event": ("Events", "event"),
                }

                if model_filter.lower() in model_map:
                    app_label, model = model_map[model_filter.lower()]
                    content_type = ContentType.objects.get(
                        app_label=app_label.lower(), model=model
                    )
                    queryset = queryset.filter(content_type=content_type)
                else:
                    return Response(
                        {
                            "error": f"Invalid model. Must be one of: {', '.join(model_map.keys())}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except ContentType.DoesNotExist:
                return Response(
                    {"error": "ContentType not found"}, status=status.HTTP_404_NOT_FOUND
                )

        serializer = CustomFieldDefinitionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new custom field definition"""
        serializer = CustomFieldDefinitionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_view(
    {
        "get": doc_retrieve(
            response=CustomFieldDefinitionSerializer,
            description="Retrieve a custom field definition by ID",
            tags=["Custom Fields"],
        ),
        "put": doc_update(
            request=CustomFieldDefinitionSerializer,
            response=CustomFieldDefinitionSerializer,
            description="Update a custom field definition by ID",
            tags=["Custom Fields"],
        ),
        "patch": doc_update(
            request=CustomFieldDefinitionSerializer,
            response=CustomFieldDefinitionSerializer,
            description="Partially update a custom field definition by ID",
            tags=["Custom Fields"],
        ),
        "delete": doc_destroy(
            description="Delete a custom field definition by ID (and all its values)",
            tags=["Custom Fields"],
        ),
    }
)
class CustomFieldDefinitionDetailView(APIView):
    """
    GET: Retrieve a custom field definition
    PUT/PATCH: Update a custom field definition
    DELETE: Delete a custom field definition

    Query Params:
    - event_id: Optional - UUID of the event (for validation)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Retrieve a specific custom field definition"""
        event_id = request.query_params.get("event_id")
        if event_id:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk, event_id=event_id)
        else:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        serializer = CustomFieldDefinitionSerializer(field_def)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """Update a custom field definition"""
        event_id = request.query_params.get("event_id") or request.data.get("event_id")
        if event_id:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk, event_id=event_id)
        else:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        serializer = CustomFieldDefinitionSerializer(
            field_def, data=request.data, partial=False
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        """Partially update a custom field definition"""
        event_id = request.query_params.get("event_id") or request.data.get("event_id")
        if event_id:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk, event_id=event_id)
        else:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        serializer = CustomFieldDefinitionSerializer(
            field_def, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a custom field definition (and all its values)"""
        event_id = request.query_params.get("event_id")
        if event_id:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk, event_id=event_id)
        else:
            field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        field_def.delete()
        return Response(
            {"message": "Custom field definition deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventRegistrationWithCustomFieldsSerializer,
            description="Get all custom field values for a specific event registration",
            tags=["Event Registration Custom Fields"],
        ),
        "post": doc_create(
            request=BulkCustomFieldValueSerializer,
            response={"message": "string", "updated_fields": "array"},
            description="Bulk set/update custom field values for an event registration",
            tags=["Event Registration Custom Fields"],
        ),
    }
)
class EventRegistrationCustomFieldValueView(APIView):
    """
    GET: Get all custom field values for a specific registration
    POST: Set/update custom field values for a registration (bulk update)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, registration_id):
        """Get all custom field values for a registration"""
        registration = get_object_or_404(EventRegistration, pk=registration_id)
        serializer = EventRegistrationWithCustomFieldsSerializer(registration)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request, registration_id):
        """
        Bulk set/update custom field values for a registration.

        Request body:
        {
            "custom_fields": {
                "field_name_1": "value1",
                "field_name_2": "value2"
            }
        }
        """
        registration = get_object_or_404(EventRegistration, pk=registration_id)

        # Validate request data
        serializer = BulkCustomFieldValueSerializer(
            data={
                "registration_id": str(registration_id),
                "event_id": str(registration.event.id),
                "custom_fields": request.data.get("custom_fields", {}),
            }
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        custom_fields = serializer.validated_data["custom_fields"]
        content_type = ContentType.objects.get_for_model(EventRegistration)

        updated_fields = []

        # Update or create each custom field value
        for field_name, value in custom_fields.items():
            try:
                # Get the field definition with event scoping
                field_def = CustomFieldDefinition.objects.get(
                    name=field_name,
                    content_type=content_type,
                    event=registration.event
                )

                # Update or create the value
                custom_value, created = CustomFieldValue.objects.update_or_create(
                    definition=field_def,
                    content_type=content_type,
                    object_id=registration.id,
                    defaults={"value": value},
                )

                updated_fields.append(
                    {
                        "field": field_name,
                        "label": field_def.label,
                        "value": value,
                        "created": created,
                    }
                )

            except CustomFieldDefinition.DoesNotExist:
                return Response(
                    {"error": f"Custom field '{field_name}' not found for this event"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(
            {
                "message": "Custom fields updated successfully",
                "updated_fields": updated_fields,
            },
            status=status.HTTP_200_OK,
        )


@document_api_view(
    {
        "get": doc_retrieve(
            response=CustomFieldValueSerializer,
            description="Get a specific custom field value for an event registration",
            tags=["Event Registration Custom Fields"],
        ),
        "put": doc_update(
            request={"value": "string"},
            response=CustomFieldValueSerializer,
            description="Update a specific custom field value for an event registration",
            tags=["Event Registration Custom Fields"],
        ),
        "delete": doc_destroy(
            description="Delete a specific custom field value for an event registration",
            tags=["Event Registration Custom Fields"],
        ),
    }
)
class EventRegistrationCustomFieldValueDetailView(APIView):
    """
    GET: Get a specific custom field value
    PUT/PATCH: Update a specific custom field value
    DELETE: Delete a specific custom field value
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, registration_id, field_name):
        """Get a specific custom field value for a registration"""
        registration = get_object_or_404(EventRegistration, pk=registration_id)
        content_type = ContentType.objects.get_for_model(EventRegistration)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=registration.event
            )
            custom_value = CustomFieldValue.objects.get(
                definition=field_def,
                content_type=content_type,
                object_id=registration.id,
            )
            serializer = CustomFieldValueSerializer(custom_value)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomFieldValue.DoesNotExist:
            return Response(
                {"error": f"No value set for field '{field_name}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def put(self, request, registration_id, field_name):
        """Update a specific custom field value"""
        registration = get_object_or_404(EventRegistration, pk=registration_id)
        content_type = ContentType.objects.get_for_model(EventRegistration)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=registration.event
            )

            custom_value, created = CustomFieldValue.objects.update_or_create(
                definition=field_def,
                content_type=content_type,
                object_id=registration.id,
                defaults={"value": request.data.get("value", "")},
            )

            serializer = CustomFieldValueSerializer(custom_value)
            return Response(
                {
                    "message": "Value updated" if not created else "Value created",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def delete(self, request, registration_id, field_name):
        """Delete a specific custom field value"""
        registration = get_object_or_404(EventRegistration, pk=registration_id)
        content_type = ContentType.objects.get_for_model(EventRegistration)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=registration.event
            )
            custom_value = CustomFieldValue.objects.get(
                definition=field_def,
                content_type=content_type,
                object_id=registration.id,
            )
            custom_value.delete()
            return Response(
                {"message": f"Value for '{field_name}' deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomFieldValue.DoesNotExist:
            return Response(
                {"error": f"No value set for field '{field_name}'"},
                status=status.HTTP_404_NOT_FOUND,
            )


@document_api_view(
    {
        "get": doc_list(
            response={
                "event_id": "uuid",
                "event_name": "string",
                "field_definitions": "array",
                "registrations": "array",
                "total_registrations": "integer",
            },
            description="Get all registrations for an event with their custom field values (useful for displaying in tables)",
            tags=["Event Registration Custom Fields"],
        ),
    }
)
class EventCustomFieldValuesListView(APIView):
    """
    GET: Get all registrations for an event with their custom field values
    Useful for displaying all registrations in a table with custom columns
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        """Get all registrations for an event with custom fields"""
        from Events.models.event_model import Event

        event = get_object_or_404(Event, pk=event_id)
        registrations = (
            EventRegistration.objects.filter(event=event)
            .select_related("guest", "event")
            .prefetch_related("custom_field_values__definition")
        )

        serializer = EventRegistrationWithCustomFieldsSerializer(
            registrations, many=True
        )

        # Also get the field definitions for this event
        content_type = ContentType.objects.get_for_model(EventRegistration)
        field_definitions = CustomFieldDefinition.objects.filter(
            event=event,
            content_type=content_type
        )
        field_def_serializer = CustomFieldDefinitionSerializer(
            field_definitions, many=True
        )

        return Response(
            {
                "event_id": str(event.id),
                "event_name": event.name,
                "field_definitions": field_def_serializer.data,
                "registrations": serializer.data,
                "total_registrations": registrations.count(),
            },
            status=status.HTTP_200_OK,
        )


# ─── Helper Functions ────────────────────────────────────────────────


def get_event_from_instance(instance):
    """
    Get the event from different model instances.
    Handles different relationships to Event model.
    """
    from Events.models.event_model import Event

    # If instance is Event itself
    if isinstance(instance, Event):
        return instance

    # Direct event FK (EventRegistration, Session, Accommodation, TravelDetail)
    if hasattr(instance, 'event') and instance.event:
        return instance.event

    # Through session (SessionRegistration)
    if hasattr(instance, 'session') and hasattr(instance.session, 'event'):
        return instance.session.event

    return None


# ─── Generic Custom Field Views ──────────────────────────────────────


class GenericCustomFieldValueView(APIView):
    """
    Generic view for managing custom field values on any model instance.
    Subclasses should define model_class and instance_param_name.
    """
    permission_classes = [IsAuthenticated]
    model_class = None  # Override in subclass
    instance_param_name = "instance_id"  # Override if needed

    def get_instance(self, instance_id):
        """Get the model instance by ID"""
        return get_object_or_404(self.model_class, pk=instance_id)

    def get(self, request, **kwargs):
        """Get all custom field values for an instance"""
        instance_id = kwargs.get(self.instance_param_name)
        instance = self.get_instance(instance_id)

        # Get custom field values
        custom_values = instance.custom_field_values.select_related("definition").all()
        custom_fields = {
            cv.definition.name: {
                "label": cv.definition.label,
                "value": cv.value,
                "type": cv.definition.field_type,
                "value_id": str(cv.id),
            }
            for cv in custom_values
        }

        return Response({
            "instance_id": str(instance.id),
            "custom_fields": custom_fields
        }, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request, **kwargs):
        """Bulk set/update custom field values for an instance"""
        instance_id = kwargs.get(self.instance_param_name)
        instance = self.get_instance(instance_id)
        event = get_event_from_instance(instance)

        if not event:
            return Response(
                {"error": "Could not determine event for this instance"},
                status=status.HTTP_400_BAD_REQUEST
            )

        custom_fields = request.data.get("custom_fields", {})
        content_type = ContentType.objects.get_for_model(self.model_class)
        updated_fields = []

        for field_name, value in custom_fields.items():
            try:
                # Get the field definition with event scoping
                field_def = CustomFieldDefinition.objects.get(
                    name=field_name,
                    content_type=content_type,
                    event=event
                )

                # Update or create the value
                custom_value, created = CustomFieldValue.objects.update_or_create(
                    definition=field_def,
                    content_type=content_type,
                    object_id=instance.id,
                    defaults={"value": value},
                )

                updated_fields.append({
                    "field": field_name,
                    "label": field_def.label,
                    "value": value,
                    "created": created,
                })

            except CustomFieldDefinition.DoesNotExist:
                return Response(
                    {"error": f"Custom field '{field_name}' not found for this event"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response({
            "message": "Custom fields updated successfully",
            "updated_fields": updated_fields,
        }, status=status.HTTP_200_OK)


class GenericCustomFieldValueDetailView(APIView):
    """
    Generic view for managing a single custom field value on any model instance.
    Subclasses should define model_class and instance_param_name.
    """
    permission_classes = [IsAuthenticated]
    model_class = None  # Override in subclass
    instance_param_name = "instance_id"  # Override if needed

    def get_instance(self, instance_id):
        """Get the model instance by ID"""
        return get_object_or_404(self.model_class, pk=instance_id)

    def get(self, request, field_name, **kwargs):
        """Get a specific custom field value"""
        instance_id = kwargs.get(self.instance_param_name)
        instance = self.get_instance(instance_id)
        event = get_event_from_instance(instance)
        content_type = ContentType.objects.get_for_model(self.model_class)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=event
            )
            custom_value = CustomFieldValue.objects.get(
                definition=field_def,
                content_type=content_type,
                object_id=instance.id,
            )
            serializer = CustomFieldValueSerializer(custom_value)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomFieldValue.DoesNotExist:
            return Response(
                {"error": f"No value set for field '{field_name}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def put(self, request, field_name, **kwargs):
        """Update a specific custom field value"""
        instance_id = kwargs.get(self.instance_param_name)
        instance = self.get_instance(instance_id)
        event = get_event_from_instance(instance)
        content_type = ContentType.objects.get_for_model(self.model_class)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=event
            )

            custom_value, created = CustomFieldValue.objects.update_or_create(
                definition=field_def,
                content_type=content_type,
                object_id=instance.id,
                defaults={"value": request.data.get("value", "")},
            )

            serializer = CustomFieldValueSerializer(custom_value)
            return Response({
                "message": "Value updated" if not created else "Value created",
                "data": serializer.data,
            }, status=status.HTTP_200_OK)

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def delete(self, request, field_name, **kwargs):
        """Delete a specific custom field value"""
        instance_id = kwargs.get(self.instance_param_name)
        instance = self.get_instance(instance_id)
        event = get_event_from_instance(instance)
        content_type = ContentType.objects.get_for_model(self.model_class)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name,
                content_type=content_type,
                event=event
            )
            custom_value = CustomFieldValue.objects.get(
                definition=field_def,
                content_type=content_type,
                object_id=instance.id,
            )
            custom_value.delete()
            return Response(
                {"message": f"Value for '{field_name}' deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )

        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"error": f"Custom field '{field_name}' not found for this event"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomFieldValue.DoesNotExist:
            return Response(
                {"error": f"No value set for field '{field_name}'"},
                status=status.HTTP_404_NOT_FOUND,
            )


# ─── Session Custom Fields ───────────────────────────────────────────


@document_api_view({
    "get": doc_retrieve(
        response={"instance_id": "uuid", "custom_fields": "object"},
        description="Get all custom field values for a session",
        tags=["Session Custom Fields"],
    ),
    "post": doc_create(
        request={"custom_fields": "object"},
        response={"message": "string", "updated_fields": "array"},
        description="Bulk set/update custom field values for a session",
        tags=["Session Custom Fields"],
    ),
})
class SessionCustomFieldValueView(GenericCustomFieldValueView):
    """Custom field values for Session"""
    instance_param_name = "session_id"

    def get_instance(self, instance_id):
        from Events.models.session_model import Session
        return get_object_or_404(Session, pk=instance_id)

    @property
    def model_class(self):
        from Events.models.session_model import Session
        return Session


@document_api_view({
    "get": doc_retrieve(
        response=CustomFieldValueSerializer,
        description="Get a specific custom field value for a session",
        tags=["Session Custom Fields"],
    ),
    "put": doc_update(
        request={"value": "string"},
        response=CustomFieldValueSerializer,
        description="Update a specific custom field value for a session",
        tags=["Session Custom Fields"],
    ),
    "delete": doc_destroy(
        description="Delete a specific custom field value for a session",
        tags=["Session Custom Fields"],
    ),
})
class SessionCustomFieldValueDetailView(GenericCustomFieldValueDetailView):
    """Custom field value detail for Session"""
    instance_param_name = "session_id"

    def get_instance(self, instance_id):
        from Events.models.session_model import Session
        return get_object_or_404(Session, pk=instance_id)

    @property
    def model_class(self):
        from Events.models.session_model import Session
        return Session


# ─── Accommodation Custom Fields ─────────────────────────────────────


@document_api_view({
    "get": doc_retrieve(
        response={"instance_id": "uuid", "custom_fields": "object"},
        description="Get all custom field values for an accommodation",
        tags=["Accommodation Custom Fields"],
    ),
    "post": doc_create(
        request={"custom_fields": "object"},
        response={"message": "string", "updated_fields": "array"},
        description="Bulk set/update custom field values for an accommodation",
        tags=["Accommodation Custom Fields"],
    ),
})
class AccommodationCustomFieldValueView(GenericCustomFieldValueView):
    """Custom field values for Accommodation"""
    instance_param_name = "accommodation_id"

    def get_instance(self, instance_id):
        from Logistics.models.accomodation_models import Accommodation
        return get_object_or_404(Accommodation, pk=instance_id)

    @property
    def model_class(self):
        from Logistics.models.accomodation_models import Accommodation
        return Accommodation


@document_api_view({
    "get": doc_retrieve(
        response=CustomFieldValueSerializer,
        description="Get a specific custom field value for an accommodation",
        tags=["Accommodation Custom Fields"],
    ),
    "put": doc_update(
        request={"value": "string"},
        response=CustomFieldValueSerializer,
        description="Update a specific custom field value for an accommodation",
        tags=["Accommodation Custom Fields"],
    ),
    "delete": doc_destroy(
        description="Delete a specific custom field value for an accommodation",
        tags=["Accommodation Custom Fields"],
    ),
})
class AccommodationCustomFieldValueDetailView(GenericCustomFieldValueDetailView):
    """Custom field value detail for Accommodation"""
    instance_param_name = "accommodation_id"

    def get_instance(self, instance_id):
        from Logistics.models.accomodation_models import Accommodation
        return get_object_or_404(Accommodation, pk=instance_id)

    @property
    def model_class(self):
        from Logistics.models.accomodation_models import Accommodation
        return Accommodation


# ─── TravelDetail Custom Fields ──────────────────────────────────────


@document_api_view({
    "get": doc_retrieve(
        response={"instance_id": "uuid", "custom_fields": "object"},
        description="Get all custom field values for a travel detail",
        tags=["TravelDetail Custom Fields"],
    ),
    "post": doc_create(
        request={"custom_fields": "object"},
        response={"message": "string", "updated_fields": "array"},
        description="Bulk set/update custom field values for a travel detail",
        tags=["TravelDetail Custom Fields"],
    ),
})
class TravelDetailCustomFieldValueView(GenericCustomFieldValueView):
    """Custom field values for TravelDetail"""
    instance_param_name = "traveldetail_id"

    def get_instance(self, instance_id):
        from Logistics.models.travel_details_models import TravelDetail
        return get_object_or_404(TravelDetail, pk=instance_id)

    @property
    def model_class(self):
        from Logistics.models.travel_details_models import TravelDetail
        return TravelDetail


@document_api_view({
    "get": doc_retrieve(
        response=CustomFieldValueSerializer,
        description="Get a specific custom field value for a travel detail",
        tags=["TravelDetail Custom Fields"],
    ),
    "put": doc_update(
        request={"value": "string"},
        response=CustomFieldValueSerializer,
        description="Update a specific custom field value for a travel detail",
        tags=["TravelDetail Custom Fields"],
    ),
    "delete": doc_destroy(
        description="Delete a specific custom field value for a travel detail",
        tags=["TravelDetail Custom Fields"],
    ),
})
class TravelDetailCustomFieldValueDetailView(GenericCustomFieldValueDetailView):
    """Custom field value detail for TravelDetail"""
    instance_param_name = "traveldetail_id"

    def get_instance(self, instance_id):
        from Logistics.models.travel_details_models import TravelDetail
        return get_object_or_404(TravelDetail, pk=instance_id)

    @property
    def model_class(self):
        from Logistics.models.travel_details_models import TravelDetail
        return TravelDetail


# ─── Event Custom Fields ─────────────────────────────────────────────


@document_api_view({
    "get": doc_retrieve(
        response={"instance_id": "uuid", "custom_fields": "object"},
        description="Get all custom field values for an event",
        tags=["Event Custom Fields"],
    ),
    "post": doc_create(
        request={"custom_fields": "object"},
        response={"message": "string", "updated_fields": "array"},
        description="Bulk set/update custom field values for an event",
        tags=["Event Custom Fields"],
    ),
})
class EventCustomFieldValueView(GenericCustomFieldValueView):
    """Custom field values for Event"""
    instance_param_name = "event_id"

    def get_instance(self, instance_id):
        from Events.models.event_model import Event
        return get_object_or_404(Event, pk=instance_id)

    @property
    def model_class(self):
        from Events.models.event_model import Event
        return Event


@document_api_view({
    "get": doc_retrieve(
        response=CustomFieldValueSerializer,
        description="Get a specific custom field value for an event",
        tags=["Event Custom Fields"],
    ),
    "put": doc_update(
        request={"value": "string"},
        response=CustomFieldValueSerializer,
        description="Update a specific custom field value for an event",
        tags=["Event Custom Fields"],
    ),
    "delete": doc_destroy(
        description="Delete a specific custom field value for an event",
        tags=["Event Custom Fields"],
    ),
})
class EventCustomFieldValueDetailView(GenericCustomFieldValueDetailView):
    """Custom field value detail for Event"""
    instance_param_name = "event_id"

    def get_instance(self, instance_id):
        from Events.models.event_model import Event
        return get_object_or_404(Event, pk=instance_id)

    @property
    def model_class(self):
        from Events.models.event_model import Event
        return Event
