from rest_framework import serializers
from Events.models.staff_event_field_permissions import (
    UserEventAccommodationFieldPermission,
    UserEventEventRegistrationFieldPermission,
    UserEventFieldPermission,
    UserEventGuestFieldPermission,
    UserEventSessionFieldPermission,
    UserEventTravelDetailFieldPermission,
)


class EventFieldPermissionSerializer(serializers.ModelSerializer):
    event_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventFieldPermission
        fields = ["id", "user", "event", "event_field", "event_field_detail"]

    def get_event_field_detail(self, obj):
        ef = obj.event_field
        return {"id": ef.id, "name": ef.name, "label": ef.label}


class GuestFieldPermissionSerializer(serializers.ModelSerializer):
    guest_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventGuestFieldPermission
        fields = ["id", "user", "event", "guest_field", "guest_field_detail"]

    def get_guest_field_detail(self, obj):
        gf = obj.guest_field
        return {"id": gf.id, "name": gf.name, "label": gf.label}


class SessionFieldPermissionSerializer(serializers.ModelSerializer):
    session_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventSessionFieldPermission
        fields = ["id", "user", "event", "session_field", "session_field_detail"]

    def get_session_field_detail(self, obj):
        sf = obj.session_field
        return {"id": sf.id, "name": sf.name, "label": sf.label}


class TravelDetailFieldPermissionSerializer(serializers.ModelSerializer):
    traveldetail_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventTravelDetailFieldPermission
        fields = [
            "id",
            "user",
            "event",
            "traveldetail_field",
            "traveldetail_field_detail",
        ]

    def get_traveldetail_field_detail(self, obj):
        tf = obj.traveldetail_field
        return {"id": tf.id, "name": tf.name, "label": tf.label}


class EventRegistrationFieldPermissionSerializer(serializers.ModelSerializer):
    eventregistration_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventEventRegistrationFieldPermission
        fields = [
            "id",
            "user",
            "event",
            "eventregistration_field",
            "eventregistration_field_detail",
        ]

    def get_eventregistration_field_detail(self, obj):
        ef = obj.eventregistration_field
        return {"id": ef.id, "name": ef.name, "label": ef.label}


class AccommodationFieldPermissionSerializer(serializers.ModelSerializer):
    accommodation_field_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserEventAccommodationFieldPermission
        fields = [
            "id",
            "user",
            "event",
            "accommodation_field",
            "accommodation_field_detail",
        ]

    def get_accommodation_field_detail(self, obj):
        af = obj.accommodation_field
        return {"id": af.id, "name": af.name, "label": af.label}
