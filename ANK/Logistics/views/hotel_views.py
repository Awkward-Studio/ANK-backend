from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from Logistics.models.hotel_models import EventHotel, EventHotelRoomType
from Logistics.models.hotel_models import Hotel
from Logistics.serializers.hotel_serializers import (
    EventHotelRoomTypeSerializer,
    EventHotelSerializer,
    HotelSerializer,
)

from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=HotelSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by hotel name"),
            ],
            description="List all hotels",
            tags=["Hotels"],
        ),
        "post": doc_create(
            request=HotelSerializer,
            response=HotelSerializer,
            description="Create a new hotel",
            tags=["Hotels"],
        ),
    }
)
class HotelList(APIView):
    def get(self, request):
        try:
            qs = Hotel.objects.all()
            return Response(HotelSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching hotels", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = HotelSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            hotel = ser.save()
            return Response(HotelSerializer(hotel).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=HotelSerializer,
            description="Retrieve a hotel by ID",
            tags=["Hotels"],
        ),
        "put": doc_update(
            request=HotelSerializer,
            response=HotelSerializer,
            description="Update a hotel by ID",
            tags=["Hotels"],
        ),
        "delete": doc_destroy(description="Delete a hotel by ID", tags=["Hotels"]),
    }
)
class HotelDetail(APIView):
    def get(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            return Response(HotelSerializer(hotel).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            ser = HotelSerializer(hotel, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            hotel = ser.save()
            return Response(HotelSerializer(hotel).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            hotel = get_object_or_404(Hotel, pk=pk)
            hotel.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event UUID"),
                query_param("hotel", "uuid", False, "Filter by hotel UUID"),
            ],
            description="List all event-hotel associations",
            tags=["Event Hotels"],
        ),
        "post": doc_create(
            request=EventHotelSerializer,
            response=EventHotelSerializer,
            description="Associate a hotel with an event",
            tags=["Event Hotels"],
        ),
    }
)
class EventHotelList(APIView):
    def get(self, request):
        try:
            qs = EventHotel.objects.all()
            event = request.GET.get("event")
            hotel = request.GET.get("hotel")
            if event:
                qs = qs.filter(event__id=event)
            if hotel:
                qs = qs.filter(hotel__id=hotel)
            return Response(EventHotelSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event hotels", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventHotelSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            event_hotel = ser.save()
            return Response(
                EventHotelSerializer(event_hotel).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventHotelSerializer,
            description="Retrieve an event-hotel association by ID",
            tags=["Event Hotels"],
        ),
        "put": doc_update(
            request=EventHotelSerializer,
            response=EventHotelSerializer,
            description="Update an event-hotel association by ID",
            tags=["Event Hotels"],
        ),
        "delete": doc_destroy(
            description="Delete an event-hotel association by ID", tags=["Event Hotels"]
        ),
    }
)
class EventHotelDetail(APIView):
    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventHotel, pk=pk)
            return Response(EventHotelSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventHotel, pk=pk)
            ser = EventHotelSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(EventHotelSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventHotel, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event hotel", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelRoomTypeSerializer(many=True),
            parameters=[
                query_param("event_hotel", "uuid", False, "Filter by event hotel UUID"),
                query_param("room_type", "str", False, "Filter by room type"),
            ],
            description="List all event-hotel room types",
            tags=["Event Hotel Room Types"],
        ),
        "post": doc_create(
            request=EventHotelRoomTypeSerializer,
            response=EventHotelRoomTypeSerializer,
            description="Create a new room type for an event hotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class EventHotelRoomTypeList(APIView):
    def get(self, request):
        try:
            qs = EventHotelRoomType.objects.all()
            event_hotel = request.GET.get("event_hotel")
            room_type = request.GET.get("room_type")
            if event_hotel:
                qs = qs.filter(event_hotel__id=event_hotel)
            if room_type:
                qs = qs.filter(room_type__iexact=room_type)
            return Response(EventHotelRoomTypeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room types", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventHotelRoomTypeSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            room_type = ser.save()
            return Response(
                EventHotelRoomTypeSerializer(room_type).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventHotelRoomTypeSerializer,
            description="Retrieve an event hotel room type by ID",
            tags=["Event Hotel Room Types"],
        ),
        "put": doc_update(
            request=EventHotelRoomTypeSerializer,
            response=EventHotelRoomTypeSerializer,
            description="Update an event hotel room type by ID",
            tags=["Event Hotel Room Types"],
        ),
        "delete": doc_destroy(
            description="Delete an event hotel room type by ID",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class EventHotelRoomTypeDetail(APIView):
    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventHotelRoomType, pk=pk)
            return Response(EventHotelRoomTypeSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventHotelRoomType, pk=pk)
            ser = EventHotelRoomTypeSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(EventHotelRoomTypeSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventHotelRoomType, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=HotelSerializer(many=True),
            parameters=[query_param("event", "uuid", True, "Event UUID")],
            description="List all hotels for a specific event",
            tags=["Hotels"],
        ),
    }
)
class EventHotelsByEventAPIView(APIView):
    def get(self, request):
        event_id = request.GET.get("event")
        if not event_id:
            return Response({"detail": "Event UUID required"}, status=400)
        try:
            event_hotels = EventHotel.objects.filter(event__id=event_id)
            hotels = [eh.hotel for eh in event_hotels.select_related("hotel")]
            return Response(HotelSerializer(hotels, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching hotels for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelRoomTypeSerializer(many=True),
            parameters=[query_param("event_hotel", "uuid", True, "EventHotel UUID")],
            description="List all room types for an event hotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class RoomTypesByEventHotelAPIView(APIView):
    def get(self, request):
        event_hotel_id = request.GET.get("event_hotel")
        if not event_hotel_id:
            return Response({"detail": "EventHotel UUID required"}, status=400)
        try:
            qs = EventHotelRoomType.objects.filter(event_hotel__id=event_hotel_id)
            return Response(EventHotelRoomTypeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room types", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventHotelRoomTypeSerializer,
            description="Get room type availability for an event hotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class RoomTypeAvailabilityAPIView(APIView):
    def get(self, request, event_hotel_id, room_type):
        try:
            room = EventHotelRoomType.objects.get(
                event_hotel__id=event_hotel_id, room_type=room_type
            )
            return Response(EventHotelRoomTypeSerializer(room).data)
        except EventHotelRoomType.DoesNotExist:
            return Response({"detail": "Room type not found."}, status=404)
        except Exception as e:
            return Response(
                {"detail": "Error fetching availability", "error": str(e)},
                status=500,
            )


@document_api_view(
    {
        "put": doc_update(
            request=None,  # customize as needed
            response=EventHotelRoomTypeSerializer(many=True),
            description="Bulk update available_count for multiple room types in an event hotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class BulkRoomAvailabilityAPIView(APIView):
    def put(self, request):
        updates = request.data.get("room_updates", [])
        if not isinstance(updates, list):
            return Response({"detail": "room_updates should be a list"}, status=400)
        updated = []
        for upd in updates:
            pk = upd.get("id")
            count = upd.get("available_count")
            if not pk or count is None:
                continue
            try:
                room = EventHotelRoomType.objects.get(pk=pk)
                room.available_count = count
                room.save()
                updated.append(room)
            except EventHotelRoomType.DoesNotExist:
                continue
        return Response(EventHotelRoomTypeSerializer(updated, many=True).data)
