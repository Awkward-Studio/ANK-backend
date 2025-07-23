from rest_framework import serializers
from Logistics.models.accomodation_models import Hotel
from Logistics.models.accomodation_models import Accommodation
from Events.models.event_registration_model import ExtraAttendee


class AccommodationSerializer(serializers.ModelSerializer):
    hotel = serializers.PrimaryKeyRelatedField(queryset=Hotel.objects.all())
    extra_attendee = serializers.PrimaryKeyRelatedField(
        queryset=ExtraAttendee.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Accommodation
        fields = [
            "id",
            "event_registration",
            "session_registration",
            "hotel",
            "sharing_with",
            "room_count",
            "room_type",
            "bed_type",
            "check_in",
            "check_out",
            "rooming_remarks",
            "extra_attendee",
        ]

    def validate(self, data):
        extra_attendee = data.get("extra_attendee")
        er = data.get("event_registration")
        sr = data.get("session_registration")

        if extra_attendee:
            # ensure they didn’t also pass registration FKs
            if er or sr:
                raise serializers.ValidationError(
                    "When specifying attendee, do NOT set event_registration or session_registration."
                )
            return data
        # enforce exactly one FK is provided
        if not bool(er) ^ bool(sr):
            raise serializers.ValidationError(
                "Provide exactly one of event_registration or session_registration when no attendee is given."
            )
        return data
