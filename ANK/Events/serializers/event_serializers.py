from rest_framework import serializers
from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration
from Guest.models import Guest


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "name", "location", "venue", "start_date", "end_date"]


class EventRegistrationSerializer(serializers.ModelSerializer):
    guest = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all())
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())

    class Meta:
        model = EventRegistration
        fields = ["id", "guest", "event", "rsvp_status", "initiated_on", "responded_on"]
        read_only_fields = ["initiated_on"]
