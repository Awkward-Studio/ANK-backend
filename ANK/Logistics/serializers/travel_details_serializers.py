from rest_framework import serializers
from Logistics.models.travel_details_models import TravelDetail


class TravelDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelDetail
        fields = [
            "id",
            "event_registration",
            "session_registration",
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
        er = data.get("event_registration")
        sr = data.get("session_registration")
        if not bool(er) ^ bool(sr):
            raise serializers.ValidationError(
                "Provide exactly one of event_registration or session_registration."
            )
        return data
