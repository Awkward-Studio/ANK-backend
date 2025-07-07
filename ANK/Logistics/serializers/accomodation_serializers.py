from rest_framework import serializers
from Logistics.models.accomodation_models import Hotel
from Logistics.models.accomodation_models import Accommodation


class AccommodationSerializer(serializers.ModelSerializer):
    hotels = serializers.PrimaryKeyRelatedField(many=True, queryset=Hotel.objects.all())

    class Meta:
        model = Accommodation
        fields = [
            "id",
            "event_registration",
            "session_registration",
            "hotels",
            "sharing_with",
            "room_count",
            "room_type",
            "bed_type",
            "check_in",
            "check_out",
            "rooming_remarks",
        ]

    def validate(self, data):
        er = data.get("event_registration")
        sr = data.get("session_registration")
        # enforce exactly one FK is provided
        if not bool(er) ^ bool(sr):
            raise serializers.ValidationError(
                "Provide exactly one of event_registration or session_registration."
            )
        return data
