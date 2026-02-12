from rest_framework import serializers
from Logistics.models.travel_details_models import TravelDetail, TravelDetailField
from Events.models.event_registration_model import EventRegistration, ExtraAttendee
from CustomField.serializers import CustomFieldMixin
from Departments.serializers_permissions import PermissionAwareSerializer


class TravelDetailSerializer(PermissionAwareSerializer, CustomFieldMixin, serializers.ModelSerializer):
    event_registrations = serializers.PrimaryKeyRelatedField(
        queryset=EventRegistration.objects.all(), many=True, required=False
    )
    extra_attendees = serializers.PrimaryKeyRelatedField(
        queryset=ExtraAttendee.objects.all(), many=True, required=False
    )
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = TravelDetail
        fields = [
            "id",
            "event",
            "event_registrations",
            "extra_attendees",
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
            "departure_time",
            "source_departure_time",
            "departure_details",
            "departure_flight_number",
            "departure_airline",
            "departure_pnr",
            "flight_number",
            "airline",
            "pnr",
            "custom_fields",
        ]

    def validate(self, data):
        ers = data.get("event_registrations", [])
        eas = data.get("extra_attendees", [])
        if not ers and not eas:
            raise serializers.ValidationError(
                "At least one event registration or extra attendee must be assigned."
            )
        return data

    def create(self, validated_data):
        ers = validated_data.pop("event_registrations", [])
        eas = validated_data.pop("extra_attendees", [])
        td = TravelDetail.objects.create(**validated_data)
        if ers:
            td.event_registrations.set(ers)
        if eas:
            td.extra_attendees.set(eas)
        return td

    def update(self, instance, validated_data):
        ers = validated_data.pop("event_registrations", None)
        eas = validated_data.pop("extra_attendees", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if ers is not None:
            instance.event_registrations.set(ers)
        if eas is not None:
            instance.extra_attendees.set(eas)
        return instance


class TravelDetailFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelDetailField
        fields = ["id", "name", "label"]


# class TravelDetailSerializer(serializers.ModelSerializer):

#     class Meta:
#         model = TravelDetail
#         fields = [
#             "id",
#             "event_id",
#             "event_registration",
#             "session_registration",
#             "extra_attendee",
#             "travel_type",
#             "arrival",
#             "arrival_date",
#             "arrival_details",
#             "arrival_time",
#             "hotel_arrival_time",
#             "hotel_departure_time",
#             "return_travel",
#             "departure",
#             "departure_date",
#             "departure_details",
#         ]

#     def validate(self, data):
#         extra_attendee = data.get("extra_attendee")
#         er = data.get("event_registration")
#         sr = data.get("session_registration")

#         if extra_attendee:
#             # ensure they didn’t also pass registration FKs
#             if er or sr:
#                 raise serializers.ValidationError(
#                     "When specifying attendee, do NOT set event_registration or session_registration."
#                 )
#             return data
#         # enforce exactly one FK is provided
#         if not bool(er) ^ bool(sr):
#             raise serializers.ValidationError(
#                 "Provide exactly one of event_registration or session_registration when no attendee is given."
#             )
#         return data
