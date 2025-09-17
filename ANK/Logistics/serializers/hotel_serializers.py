from rest_framework import serializers
from Logistics.models.hotel_models import (
    Hotel,
    HotelRoomType,
    EventHotel,
    EventHotelRoomType,
)


class HotelRoomTypeSerializer(serializers.ModelSerializer):
    # For standalone creation via endpoint
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(), source="hotel", write_only=True, required=False
    )

    class Meta:
        model = HotelRoomType
        fields = ["id", "name", "total_count", "hotel_id"]


class HotelRoomTypeNestedCreateSerializer(serializers.ModelSerializer):
    """Used only when creating room types inside Hotel.create().
    No hotel_id here; parent will attach hotel.
    """

    class Meta:
        model = HotelRoomType
        fields = ["name", "total_count"]


class HotelSerializer(serializers.ModelSerializer):
    # Read: show related room types via related_name="room_types"
    room_types = HotelRoomTypeSerializer(many=True, read_only=True)

    # Write: preferred input key
    room_types_input = HotelRoomTypeNestedCreateSerializer(
        many=True, write_only=True, required=False
    )

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "address",
            "country",
            "city",
            "room_types",  # read-only output
            "room_types_input",  # write-only input (preferred)
        ]

    def create(self, validated_data):
        # Primary (documented) input
        room_types_data = validated_data.pop("room_types_input", None)

        # Back-compat / ergonomic input:
        # if client sent "room_types" (your current payload), accept it for create
        if room_types_data is None:
            # self.initial_data is the raw incoming payload before validation
            candidate = self.initial_data.get("room_types")
            if isinstance(candidate, list):
                # Optionally validate the list items, keeping it minimal:
                room_types_data = []
                for item in candidate:
                    # Allow {"name": "...", "total_count": 23}
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    total = item.get("total_count", 0)
                    if name is None:
                        continue
                    room_types_data.append(
                        {"name": str(name), "total_count": int(total or 0)}
                    )
            else:
                room_types_data = []

        hotel = Hotel.objects.create(**validated_data)

        # Create nested room types (if any)
        for rt in room_types_data or []:
            HotelRoomType.objects.create(hotel=hotel, **rt)

        return hotel


class EventHotelSerializer(serializers.ModelSerializer):
    hotel = HotelSerializer(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(), source="hotel", write_only=True
    )

    class Meta:
        model = EventHotel
        fields = ["id", "event", "hotel", "hotel_id"]


class EventHotelRoomTypeSerializer(serializers.ModelSerializer):
    # Read-only nested representations for GETs
    event_hotel = EventHotelSerializer(read_only=True)
    hotel_room_type = HotelRoomTypeSerializer(read_only=True)

    # Write-only ID inputs for POST/PUT/PATCH
    event_hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=EventHotel.objects.all(), source="event_hotel", write_only=True
    )
    hotel_room_type_id = serializers.PrimaryKeyRelatedField(
        queryset=HotelRoomType.objects.all(), source="hotel_room_type", write_only=True
    )

    class Meta:
        model = EventHotelRoomType
        fields = [
            "id",
            "event_hotel",
            "event_hotel_id",
            "hotel_room_type",
            "hotel_room_type_id",
            "allocation_count",
            "available_count",
        ]

    def validate(self, attrs):
        event_hotel = attrs.get("event_hotel") or getattr(
            self.instance, "event_hotel", None
        )
        hotel_room_type = attrs.get("hotel_room_type") or getattr(
            self.instance, "hotel_room_type", None
        )
        allocation_count = attrs.get(
            "allocation_count", getattr(self.instance, "allocation_count", 0)
        )
        available_count = attrs.get(
            "available_count", getattr(self.instance, "available_count", 0)
        )

        if not event_hotel or not hotel_room_type:
            return attrs

        # Ensure consistency: room type must belong to the same hotel as event_hotel
        if hotel_room_type.hotel_id != event_hotel.hotel_id:
            raise serializers.ValidationError(
                "Hotel room type must belong to the same hotel as the event-hotel link."
            )

        if allocation_count < 0 or available_count < 0:
            raise serializers.ValidationError("Counts cannot be negative.")

        if allocation_count > hotel_room_type.total_count:
            raise serializers.ValidationError(
                "Allocation exceeds hotel's total room count for this room type."
            )

        if available_count > allocation_count:
            raise serializers.ValidationError(
                "Available count cannot exceed allocation count."
            )

        return attrs

    def create(self, validated_data):
        # Default available_count to allocation_count if not provided
        if "available_count" not in validated_data:
            validated_data["available_count"] = validated_data.get(
                "allocation_count", 0
            )
        return super().create(validated_data)
