from rest_framework import serializers
from Logistics.models.travel_details_models import TravelDetail


class TravelDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = TravelDetail
        fields = [
            "id",
            "event_id",
            "event_registration",
            "session_registration",
            "extra_attendee",
            "travel_type",
            "arrival",
            "arrival_date",
            "arrival_details",
            "arrival_time",
            "hotel_arrival_time",
            "hotel_departure_time",
            "return_travel",
            "departure",
            "departure_date",
            "departure_details",
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
