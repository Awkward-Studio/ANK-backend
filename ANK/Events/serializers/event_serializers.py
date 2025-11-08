from rest_framework import serializers
from Guest.serializers import GuestSerializer
from Events.models.event_model import Event, EventField
from Events.models.event_registration_model import (
    EventRegistration,
    EventRegistrationField,
    ExtraAttendee,
)


class EventSerializer(serializers.ModelSerializer):
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
            "client_name",
        ]


class EventFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventField
        fields = ["id", "name", "label"]


class EventRegistrationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRegistrationField
        fields = ["id", "name", "label"]


class EventRegistrationSerializer(serializers.ModelSerializer):
    guest = GuestSerializer(read_only=True)
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())

    class Meta:
        model = EventRegistration
        fields = [
            "id",
            "guest",
            "event",
            "rsvp_status",
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
        ]
        read_only_fields = ["initiated_on"]


class ExtraAttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraAttendee
        fields = ["id", "registration", "name", "phone", "photo_id"]
