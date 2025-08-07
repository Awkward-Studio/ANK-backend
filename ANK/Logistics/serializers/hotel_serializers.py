from rest_framework import serializers
from Logistics.models.hotel_models import Hotel, EventHotel, EventHotelRoomType


class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ["id", "name", "address", "location"]


class EventHotelSerializer(serializers.ModelSerializer):
    hotel = HotelSerializer(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(), source="hotel", write_only=True
    )

    class Meta:
        model = EventHotel
        fields = ["id", "event", "hotel", "hotel_id"]


class EventHotelRoomTypeSerializer(serializers.ModelSerializer):
    event_hotel = EventHotelSerializer(read_only=True)
    event_hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=EventHotel.objects.all(), source="event_hotel", write_only=True
    )

    class Meta:
        model = EventHotelRoomType
        fields = [
            "id",
            "event_hotel",
            "event_hotel_id",
            "room_type",
            "total_count",
            "available_count",
        ]
