from rest_framework import serializers
from Events.models.staff_assignment_models import (
    EventStaffAssignment,
    SessionStaffAssignment,
)
from Events.models.event_model import Event
from Events.models.session_model import Session
from Staff.models import User


class EventStaffAssignmentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())

    class Meta:
        model = EventStaffAssignment
        fields = ["id", "user", "event", "role", "assigned_on", "removed_on"]
        read_only_fields = ["assigned_on"]


class SessionStaffAssignmentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    session = serializers.PrimaryKeyRelatedField(queryset=Session.objects.all())

    class Meta:
        model = SessionStaffAssignment
        fields = ["id", "user", "session", "role", "assigned_on", "removed_on"]
        read_only_fields = ["assigned_on"]
