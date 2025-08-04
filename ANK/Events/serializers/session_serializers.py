from rest_framework import serializers
from Events.models.session_model import Session, SessionField
from Events.models.session_registration import SessionRegistration
from Guest.models import Guest
from Events.models.event_model import Event


class SessionSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())

    class Meta:
        model = Session
        fields = [
            "id",
            "event",
            "title",
            "description",
            "start_time",
            "end_time",
            "pax",
            "date",
            "location",
            "entertainment",
            "unique_string",
        ]


class SessionFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionField
        fields = ["id", "name", "label"]


class SessionRegistrationSerializer(serializers.ModelSerializer):
    guest = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all())
    session = serializers.PrimaryKeyRelatedField(queryset=Session.objects.all())

    class Meta:
        model = SessionRegistration
        fields = ["id", "guest", "session", "registered_on"]
        read_only_fields = ["registered_on"]
