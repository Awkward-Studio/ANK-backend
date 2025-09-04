from django.db import models
import uuid
from Events.models.event_model import Event


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.country}"


class HotelRoomType(models.Model):
    """
    Defines a room type for a specific hotel and its total available stock at the hotel.
    Example: ("Deluxe", total_count=40) for Hotel A.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(
        Hotel, on_delete=models.CASCADE, related_name="room_types"
    )
    name = models.CharField(max_length=100)
    total_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("hotel", "name")

    def __str__(self):
        return f"{self.name} @ {self.hotel.name} ({self.total_count})"


class EventHotel(models.Model):
    """
    Associates an Event with a Hotel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="event_hotels"
    )
    hotel = models.ForeignKey(
        Hotel, on_delete=models.CASCADE, related_name="event_hotels"
    )

    class Meta:
        unique_together = ("event", "hotel")

    def __str__(self):
        return f"{self.event_id} - {self.hotel.name}"


class EventHotelRoomType(models.Model):
    """
    Per-event allocation for a given hotel's room type.
    - allocation_count: how many rooms of this type are allocated to the event.
    - available_count: how many are currently available for assignment under this event.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_hotel = models.ForeignKey(
        EventHotel, on_delete=models.CASCADE, related_name="room_types"
    )
    hotel_room_type = models.ForeignKey(
        HotelRoomType,
        on_delete=models.CASCADE,
        related_name="event_room_types",
        null=True,
        blank=True,
    )
    allocation_count = models.PositiveIntegerField(default=0)
    available_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("event_hotel", "hotel_room_type")

    def __str__(self):
        return (
            f"{self.hotel_room_type.name} for {self.event_hotel.hotel.name} "
            f"allocated {self.allocation_count}, avail {self.available_count}"
        )
