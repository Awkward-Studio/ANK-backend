from rest_framework import serializers
from Events.models.session_model import Session, SessionField
from Events.models.session_registration import SessionRegistration
from Guest.models import Guest
from Events.models.event_model import Event
from Logistics.models.hotel_models import Hotel
from Logistics.serializers.hotel_serializers import HotelSerializer
from CustomField.serializers import CustomFieldMixin
from Departments.serializers_permissions import PermissionAwareSerializer


class SessionSerializer(PermissionAwareSerializer, CustomFieldMixin, serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    venue = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(),
        required=False,
        allow_null=True
    )
    venue_detail = HotelSerializer(source='venue', read_only=True)
    custom_fields = serializers.SerializerMethodField()

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
            "venue",
            "venue_name",
            "venue_detail",
            "unique_string",
            "custom_fields",
        ]
        read_only_fields = ['id', 'venue_detail']


class SessionFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionField
        fields = ["id", "name", "label"]


class SessionRegistrationSerializer(PermissionAwareSerializer, CustomFieldMixin, serializers.ModelSerializer):
    guest = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all())
    session = serializers.PrimaryKeyRelatedField(queryset=Session.objects.all())
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = SessionRegistration
        fields = ["id", "guest", "session", "registered_on", "custom_fields"]
        read_only_fields = ["registered_on"]
