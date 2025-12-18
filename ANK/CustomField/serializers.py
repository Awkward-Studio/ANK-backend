from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from CustomField.models import CustomFieldDefinition, CustomFieldValue


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomFieldDefinition.
    Used to define custom fields for EventRegistration (or other models).
    """

    content_type_model = serializers.CharField(
        write_only=True,
        required=False,
        help_text="Model name (e.g., 'eventregistration', 'event', 'session')",
    )
    model_name = serializers.SerializerMethodField(read_only=True)
    event_id = serializers.UUIDField(write_only=True, required=True)
    event_name = serializers.CharField(source='event.name', read_only=True)

    class Meta:
        model = CustomFieldDefinition
        fields = [
            "id",
            "name",
            "label",
            "field_type",
            "help_text",
            "content_type",
            "content_type_model",
            "model_name",
            "event",
            "event_id",
            "event_name",
        ]
        read_only_fields = ["id", "content_type", "event"]

    def get_model_name(self, obj):
        """Return the model name for display purposes"""
        return obj.content_type.model if obj.content_type else None

    def validate_name(self, value):
        """Ensure name is lowercase and uses underscores"""
        if not value.replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Field name must contain only letters, numbers, and underscores"
            )
        return value.lower()

    def create(self, validated_data):
        """Create a CustomFieldDefinition with proper ContentType and Event"""
        content_type_model = validated_data.pop(
            "content_type_model", "eventregistration"
        )
        event_id = validated_data.pop('event_id')

        # Get Event instance
        from Events.models.event_model import Event
        event = Event.objects.get(id=event_id)

        # Map model names to actual model classes
        model_map = {
            "eventregistration": "Events.EventRegistration",
            "sessionregistration": "Events.SessionRegistration",
            "accommodation": "Logistics.Accommodation",
            "traveldetail": "Logistics.TravelDetail",
            "session": "Events.Session",
            "event": "Events.Event",
        }

        # Get the app and model name
        model_path = model_map.get(content_type_model.lower())
        if not model_path:
            raise serializers.ValidationError(
                f"Invalid content_type_model. Must be one of: {', '.join(model_map.keys())}"
            )

        app_label, model = model_path.split(".")

        # Get or create ContentType
        content_type = ContentType.objects.get(
            app_label=app_label.lower(), model=model.lower()
        )

        validated_data["content_type"] = content_type
        validated_data["event"] = event
        return super().create(validated_data)


class CustomFieldValueSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomFieldValue.
    Used to store actual values for custom fields.
    """

    field_name = serializers.CharField(source="definition.name", read_only=True)
    field_label = serializers.CharField(source="definition.label", read_only=True)
    field_type = serializers.CharField(source="definition.field_type", read_only=True)

    class Meta:
        model = CustomFieldValue
        fields = [
            "id",
            "definition",
            "value",
            "field_name",
            "field_label",
            "field_type",
        ]

    def validate(self, data):
        """Validate value based on field type"""
        if "definition" in data and "value" in data:
            definition = data["definition"]
            value = data["value"]

            if definition.field_type == "number":
                try:
                    float(value)
                except ValueError:
                    raise serializers.ValidationError(
                        {
                            "value": f'Value must be a number for field "{definition.label}"'
                        }
                    )

            elif definition.field_type == "boolean":
                if value.lower() not in ["true", "false", "1", "0", "yes", "no"]:
                    raise serializers.ValidationError(
                        {
                            "value": f'Value must be boolean (true/false) for field "{definition.label}"'
                        }
                    )

            elif definition.field_type == "date":
                from datetime import datetime

                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    raise serializers.ValidationError(
                        {
                            "value": f'Value must be a valid date (ISO format) for field "{definition.label}"'
                        }
                    )

        return data


class EventRegistrationWithCustomFieldsSerializer(serializers.Serializer):
    """
    Nested serializer for EventRegistration that includes custom field values.
    This is read-only and used for GET requests to include custom fields.
    """

    registration_id = serializers.UUIDField(source="id", read_only=True)
    guest_name = serializers.CharField(source="guest.name", read_only=True)
    event_id = serializers.UUIDField(source="event.id", read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)
    rsvp_status = serializers.CharField(read_only=True)
    custom_fields = serializers.SerializerMethodField()

    def get_custom_fields(self, obj):
        """Return all custom field values as a dictionary"""
        custom_values = obj.custom_field_values.select_related("definition").all()
        return {
            cv.definition.name: {
                "label": cv.definition.label,
                "value": cv.value,
                "type": cv.definition.field_type,
                "value_id": str(cv.id),
            }
            for cv in custom_values
        }


class BulkCustomFieldValueSerializer(serializers.Serializer):
    """
    Serializer for bulk updating custom field values for a registration.
    Accepts: {"field_name": "value", "another_field": "value"}
    """

    registration_id = serializers.UUIDField(required=True)
    event_id = serializers.UUIDField(required=True)
    custom_fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=True,
        help_text="Dictionary of {field_name: value} pairs",
    )

    def validate(self, data):
        """Validate that all field names exist for the event's EventRegistration model"""
        from django.contrib.contenttypes.models import ContentType
        from Events.models.event_registration_model import EventRegistration
        from Events.models.event_model import Event

        # Verify event exists
        event_id = data['event_id']
        if not Event.objects.filter(id=event_id).exists():
            raise serializers.ValidationError({"event_id": "Event not found"})

        # Get ContentType for EventRegistration
        content_type = ContentType.objects.get_for_model(EventRegistration)

        # Get all valid field definitions for EventRegistration IN THIS EVENT
        valid_fields = CustomFieldDefinition.objects.filter(
            event_id=event_id,
            content_type=content_type
        ).values_list("name", flat=True)

        # Check if all provided field names are valid
        invalid_fields = set(data["custom_fields"].keys()) - set(valid_fields)
        if invalid_fields:
            raise serializers.ValidationError(
                {"custom_fields": f"Invalid field names for this event: {', '.join(invalid_fields)}"}
            )

        return data


class CustomFieldMixin:
    """
    Mixin to add custom_fields to any serializer.
    Automatically includes custom field values in the serialized output.
    """

    def get_custom_fields(self, obj):
        """Return all custom field values as a dictionary"""
        if not hasattr(obj, 'custom_field_values'):
            return {}

        custom_values = obj.custom_field_values.select_related("definition").all()
        return {
            cv.definition.name: {
                "label": cv.definition.label,
                "value": cv.value,
                "type": cv.definition.field_type,
                "value_id": str(cv.id),
            }
            for cv in custom_values
        }
