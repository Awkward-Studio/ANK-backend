from rest_framework import serializers
from Guest.serializers import GuestSerializer
from Events.models.event_model import Event, EventField
from Events.models.event_registration_model import (
    EventRegistration,
    EventRegistrationField,
    ExtraAttendee,
)
from Guest.models import Guest
from CustomField.serializers import CustomFieldMixin

class EventSerializer(CustomFieldMixin, serializers.ModelSerializer):
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "location",
            "venue",
            "start_date",
            "end_date",
            "pax",
            "bride_name",
            "groom_name",
            "type",
            "location_type",
            "client_name",
            "custom_fields",
        ]


class EventFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventField
        fields = ["id", "name", "label"]


class EventRegistrationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRegistrationField
        fields = ["id", "name", "label"]


class EventRegistrationSerializer(CustomFieldMixin, serializers.ModelSerializer):
    guest = GuestSerializer(read_only=True)
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    guest_id = serializers.PrimaryKeyRelatedField(
        queryset=Guest.objects.all(),
        source='guest',       # content of guest_id saves to 'guest' field
        write_only=True       # used only for input, not output
    )
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = [
            "id",
            "guest",
            "guest_id",
            "event",
            "rsvp_status",
            "logistics_status",
            "initiated_on",
            "responded_on",
            "guest_group",
            "sub_guest_group",
            "name_on_message",
            "family_salutation",
            "title",
            "estimated_pax",
            "visa_oci",
            "hamper_count",
            "additional_guest_count",
            "custom_fields",
        ]
        read_only_fields = ["initiated_on"]

    def validate_rsvp_status(self, value):
        """
        Normalize rsvp_status to lowercase for case-insensitive validation.
        Accepts: "Pending", "pending", "Yes", "yes", etc.
        """
        if value:
            # Normalize to lowercase
            normalized = value.lower()
            # Check if it's a valid choice
            valid_choices = ["not_sent", "pending", "yes", "no", "maybe"]
            if normalized not in valid_choices:
                raise serializers.ValidationError(
                    f"Invalid rsvp_status. Must be one of: {', '.join(valid_choices)}"
                )
            return normalized
        return value

    def validate_logistics_status(self, value):
        """
        Normalize logistics_status to lowercase for case-insensitive validation.
        Accepts: "Not Started", "not_started", "In Flight", "in_flight", etc.
        """
        if value:
            # Normalize to lowercase
            normalized = value.lower()
            # Check if it's a valid choice
            valid_choices = [
                "not_started",
                "in_flight",
                "landed",
                "received",
                "arrived_hotel",
                "checked_in",
            ]
            if normalized not in valid_choices:
                raise serializers.ValidationError(
                    f"Invalid logistics_status. Must be one of: {', '.join(valid_choices)}"
                )
            return normalized
        return value



class ExtraAttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraAttendee
        fields = ["id", "registration", "name", "phone", "photo_id"]
