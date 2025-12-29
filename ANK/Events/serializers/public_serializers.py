"""
Public serializers for Client View API - limited fields only.
These serializers expose only non-sensitive data safe for public access.
"""
from rest_framework import serializers
from Events.models.event_model import Event


class PublicEventSerializer(serializers.ModelSerializer):
    """Serializer for public event data - limited fields only"""

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "bride_name",
            "groom_name",
            "venue",
            "location",
            "start_date",
            "end_date",
        ]


class PublicGuestSerializer(serializers.Serializer):
    """Serializer for public guest data - limited fields only"""

    id = serializers.UUIDField()
    name = serializers.CharField()
    rsvp_status = serializers.CharField()
    estimated_pax = serializers.IntegerField()


class ClientViewSummarySerializer(serializers.Serializer):
    """Serializer for event summary statistics"""

    total_invited = serializers.IntegerField()
    total_pax = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    confirmed_pax = serializers.IntegerField()
    declined = serializers.IntegerField()
    maybe = serializers.IntegerField()
    pending = serializers.IntegerField()


class ClientViewResponseSerializer(serializers.Serializer):
    """Complete response serializer for client view endpoint"""

    event = PublicEventSerializer()
    guests = PublicGuestSerializer(many=True)
    summary = ClientViewSummarySerializer()
