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


class CustomFieldDefinitionListCreateView(APIView):
    """
    GET: List all custom field definitions (optionally filter by model)
    POST: Create a new custom field definition

    Query Params:
    - model: Filter by model name (e.g., 'eventregistration', 'event', 'session')
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all custom field definitions"""
        model_filter = request.query_params.get("model", None)

        queryset = CustomFieldDefinition.objects.all()

        if model_filter:
            try:
                # Map model names to app labels
                model_map = {
                    "eventregistration": ("Events", "eventregistration"),
                    "event": ("Events", "event"),
                    "session": ("Events", "session"),
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


class CustomFieldDefinitionDetailView(APIView):
    """
    GET: Retrieve a custom field definition
    PUT/PATCH: Update a custom field definition
    DELETE: Delete a custom field definition
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Retrieve a specific custom field definition"""
        field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        serializer = CustomFieldDefinitionSerializer(field_def)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """Update a custom field definition"""
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
        field_def = get_object_or_404(CustomFieldDefinition, pk=pk)
        field_def.delete()
        return Response(
            {"message": "Custom field definition deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
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
                # Get the field definition
                field_def = CustomFieldDefinition.objects.get(
                    name=field_name, content_type=content_type
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
                    {"error": f"Custom field '{field_name}' not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(
            {
                "message": "Custom fields updated successfully",
                "updated_fields": updated_fields,
            },
            status=status.HTTP_200_OK,
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
                name=field_name, content_type=content_type
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
                {"error": f"Custom field '{field_name}' not found"},
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
                name=field_name, content_type=content_type
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
                {"error": f"Custom field '{field_name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def delete(self, request, registration_id, field_name):
        """Delete a specific custom field value"""
        registration = get_object_or_404(EventRegistration, pk=registration_id)
        content_type = ContentType.objects.get_for_model(EventRegistration)

        try:
            field_def = CustomFieldDefinition.objects.get(
                name=field_name, content_type=content_type
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
                {"error": f"Custom field '{field_name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomFieldValue.DoesNotExist:
            return Response(
                {"error": f"No value set for field '{field_name}'"},
                status=status.HTTP_404_NOT_FOUND,
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
