from django.db import transaction
from rest_framework import serializers
from Logistics.models.accomodation_models import (
    Accommodation,
    AccommodationField,
    EventHotelRoomType,
)
from Logistics.serializers.hotel_serializers import (
    EventHotelRoomTypeSerializer,
)
from CustomField.serializers import CustomFieldMixin
from Departments.serializers_permissions import PermissionAwareSerializer


class AccommodationSerializer(PermissionAwareSerializer, CustomFieldMixin, serializers.ModelSerializer):

    event_room_type = serializers.PrimaryKeyRelatedField(
        queryset=EventHotelRoomType.objects.all()
    )
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Accommodation
        fields = [
            "id",
            "event",
            "event_hotel",
            "event_room_type",
            "event_registrations",
            "extra_attendees",
            "sharing_with",
            "room_count",
            "bed_type",
            "check_in",
            "check_out",
            "rooming_remarks",
            "created_at",
            "updated_at",
            "custom_fields",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        ers = data.get("event_registrations", [])
        eas = data.get("extra_attendees", [])
        if not ers and not eas:
            raise serializers.ValidationError(
                "At least one event registration or extra attendee must be assigned."
            )

        event_hotel = data.get("event_hotel") or getattr(
            self.instance, "event_hotel", None
        )
        event_room_type = data.get("event_room_type") or getattr(
            self.instance, "event_room_type", None
        )
        room_count = data.get("room_count", getattr(self.instance, "room_count", 1))

        if not event_hotel or not event_room_type:
            raise serializers.ValidationError(
                "event_hotel and event_room_type are required."
            )

        # Ensure the selected event_room_type belongs to the same event_hotel
        if event_room_type.event_hotel_id != event_hotel.id:
            raise serializers.ValidationError(
                "Selected event_room_type does not belong to the provided event_hotel."
            )

        if room_count <= 0:
            raise serializers.ValidationError("room_count must be a positive integer.")

        return data

    @transaction.atomic
    def create(self, validated_data):
        room_type = validated_data["event_room_type"]
        count = validated_data.get("room_count", 1)

        # Lock this room type for concurrent writes
        rt = EventHotelRoomType.objects.select_for_update().get(pk=room_type.pk)

        # OLD:
        # if rt.available_count < count:
        #     raise serializers.ValidationError("Not enough rooms available.")

        rt.available_count -= count
        rt.save(update_fields=["available_count"])
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        new_rt = validated_data.get("event_room_type", instance.event_room_type)
        new_count = validated_data.get("room_count", instance.room_count)

        old_rt = instance.event_room_type
        old_count = instance.room_count

        if new_rt != old_rt or new_count != old_count:
            rts = EventHotelRoomType.objects.select_for_update().filter(
                pk__in=[old_rt.pk, new_rt.pk]
            )
            rt_map = {rt.pk: rt for rt in rts}

            # revert previous allocation
            rt_map[old_rt.pk].available_count += old_count

            # OLD:
            # if rt_map[new_rt.pk].available_count < new_count:
            #     raise serializers.ValidationError("Not enough rooms available.")

            rt_map[new_rt.pk].available_count -= new_count

            for rt in rt_map.values():
                rt.save(update_fields=["available_count"])

        return super().update(instance, validated_data)


class AccommodationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccommodationField
        fields = ["id", "name", "label"]
