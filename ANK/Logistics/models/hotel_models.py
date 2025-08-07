from django.db import models
import uuid
from Events.models.event_model import Event


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)
    location = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class EventHotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="event_hotels"
    )
    hotel = models.ForeignKey(
        Hotel, on_delete=models.CASCADE, related_name="event_hotels"
    )


class EventHotelRoomType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_hotel = models.ForeignKey(
        EventHotel, on_delete=models.CASCADE, related_name="room_types"
    )
    room_type = models.CharField(max_length=100)
    total_count = models.PositiveIntegerField(default=0)
    available_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("event_hotel", "room_type")

    def __str__(self):
        return f"{self.room_type} ({self.available_count}/{self.total_count})"
