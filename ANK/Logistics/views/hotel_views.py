from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from Logistics.models.hotel_models import (
    Hotel,
    HotelRoomType,
    EventHotel,
    EventHotelRoomType,
)
from Logistics.serializers.hotel_serializers import (
    HotelSerializer,
    HotelRoomTypeSerializer,
    EventHotelSerializer,
    EventHotelRoomTypeSerializer,
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

# -------------------------
# Hotels
# -------------------------


@document_api_view(
    {
        "get": doc_list(
            response=HotelSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by hotel name (icontains)"),
                query_param("city", "str", False, "Filter by city (iexact)"),
                query_param("country", "str", False, "Filter by country (iexact)"),
            ],
            description="List all hotels",
            tags=["Hotels"],
        ),
        "post": doc_create(
            request=HotelSerializer,
            response=HotelSerializer,
            description=(
                "Create a new hotel. To add room types at the same time, pass "
                "`room_types_input: [{name, total_count}, ...]`."
            ),
            tags=["Hotels"],
        ),
    }
)
class HotelList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Hotel.objects.all().prefetch_related("room_types")
            name = request.GET.get("name")
            city = request.GET.get("city")
            country = request.GET.get("country")
            if name:
                qs = qs.filter(name__icontains=name)
            if city:
                qs = qs.filter(city__iexact=city)
            if country:
                qs = qs.filter(country__iexact=country)
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
            description="Update a hotel by ID (hotel fields only).",
            tags=["Hotels"],
        ),
        "delete": doc_destroy(description="Delete a hotel by ID", tags=["Hotels"]),
    }
)
class HotelDetail(APIView):
    permission_classes = [IsAuthenticated]

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
            # Only hotel fields are updated here; manage room types via RoomType endpoints.
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


# -------------------------
# Hotel Room Types (at Hotel level)
# -------------------------


@document_api_view(
    {
        "get": doc_list(
            response=HotelRoomTypeSerializer(many=True),
            parameters=[
                query_param("hotel", "uuid", False, "Filter by hotel UUID"),
                query_param("name", "str", False, "Filter by room type name (iexact)"),
            ],
            description="List hotel room types",
            tags=["Hotel Room Types"],
        ),
        "post": doc_create(
            request=HotelRoomTypeSerializer,
            response=HotelRoomTypeSerializer,
            description="Create a hotel room type (requires hotel_id).",
            tags=["Hotel Room Types"],
        ),
    }
)
class HotelRoomTypeList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = HotelRoomType.objects.all()
            hotel = request.GET.get("hotel")
            name = request.GET.get("name")
            if hotel:
                qs = qs.filter(hotel__id=hotel)
            if name:
                qs = qs.filter(name__iexact=name)
            return Response(HotelRoomTypeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room types", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = HotelRoomTypeSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            if "hotel" not in ser.validated_data and "hotel_id" not in request.data:
                return Response({"detail": "hotel_id is required"}, status=400)
            room_type = ser.save()
            return Response(
                HotelRoomTypeSerializer(room_type).data,
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
            response=HotelRoomTypeSerializer,
            description="Retrieve a hotel room type by ID",
            tags=["Hotel Room Types"],
        ),
        "put": doc_update(
            request=HotelRoomTypeSerializer,
            response=HotelRoomTypeSerializer,
            description="Update a hotel room type by ID",
            tags=["Hotel Room Types"],
        ),
        "delete": doc_destroy(
            description="Delete a hotel room type by ID", tags=["Hotel Room Types"]
        ),
    }
)
class HotelRoomTypeDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(HotelRoomType, pk=pk)
            return Response(HotelRoomTypeSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(HotelRoomType, pk=pk)
            ser = HotelRoomTypeSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(HotelRoomTypeSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(HotelRoomType, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting room type", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------
# Event ↔ Hotel
# -------------------------


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event UUID"),
                query_param("hotel", "uuid", False, "Filter by hotel UUID"),
            ],
            description="List event-hotel associations",
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
    permission_classes = [IsAuthenticated]

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
            obj = ser.save()
            return Response(
                EventHotelSerializer(obj).data, status=status.HTTP_201_CREATED
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
    permission_classes = [IsAuthenticated]

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


# -------------------------
# Event ↔ Hotel Room Types (allocations)
# -------------------------


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelRoomTypeSerializer(many=True),
            parameters=[
                query_param("event_hotel", "uuid", False, "Filter by EventHotel UUID"),
                query_param(
                    "hotel_room_type", "uuid", False, "Filter by HotelRoomType UUID"
                ),
            ],
            description="List event-hotel room type allocations",
            tags=["Event Hotel Room Types"],
        ),
        "post": doc_create(
            request=EventHotelRoomTypeSerializer,
            response=EventHotelRoomTypeSerializer,
            description=(
                "Create an allocation for an event-hotel and a hotel's room type. "
                "Provide event_hotel_id, hotel_room_type_id, allocation_count, "
                "and optionally available_count (defaults to allocation_count)."
            ),
            tags=["Event Hotel Room Types"],
        ),
    }
)
class EventHotelRoomTypeList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = EventHotelRoomType.objects.select_related(
                "event_hotel", "hotel_room_type", "event_hotel__hotel"
            )
            event_hotel = request.GET.get("event_hotel")
            hotel_room_type = request.GET.get("hotel_room_type")
            if event_hotel:
                qs = qs.filter(event_hotel__id=event_hotel)
            if hotel_room_type:
                qs = qs.filter(hotel_room_type__id=hotel_room_type)
            return Response(EventHotelRoomTypeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventHotelRoomTypeSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(
                EventHotelRoomTypeSerializer(obj).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventHotelRoomTypeSerializer,
            description="Retrieve an event-hotel room type allocation by ID",
            tags=["Event Hotel Room Types"],
        ),
        "put": doc_update(
            request=EventHotelRoomTypeSerializer,
            response=EventHotelRoomTypeSerializer,
            description="Update an event-hotel room type allocation by ID",
            tags=["Event Hotel Room Types"],
        ),
        "delete": doc_destroy(
            description="Delete an event-hotel room type allocation by ID",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class EventHotelRoomTypeDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventHotelRoomType, pk=pk)
            return Response(EventHotelRoomTypeSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocation", "error": str(e)},
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
                {"detail": "Error updating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventHotelRoomType, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------
# Custom convenience endpoints
# -------------------------


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelSerializer(many=True),
            parameters=[query_param("event", "uuid", True, "Event UUID")],
            description="List all hotels for a specific event",
            tags=["Hotels"],
        ),
    }
)
class EventHotelsByEventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        event_id = request.GET.get("event")
        if not event_id:
            return Response(
                {"detail": "Event UUID required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            qs = EventHotel.objects.filter(event_id=event_id).select_related(
                "hotel"
            )  # efficient join
            return Response(
                EventHotelSerializer(qs, many=True).data, status=status.HTTP_200_OK
            )
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
            description="List all room type allocations for an EventHotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class RoomTypesByEventHotelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        event_hotel_id = request.GET.get("event_hotel")
        if not event_hotel_id:
            return Response({"detail": "EventHotel UUID required"}, status=400)
        try:
            qs = EventHotelRoomType.objects.filter(event_hotel__id=event_hotel_id)
            return Response(EventHotelRoomTypeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching room type allocations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventHotelRoomTypeSerializer,
            description="Get availability for a named room type under an EventHotel",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class RoomTypeAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    URL expects: /.../availability/<event_hotel_id>/<room_type_name>/
    """

    def get(self, request, event_hotel_id, room_type_name):
        try:
            event_hotel = get_object_or_404(EventHotel, id=event_hotel_id)
            # Find the hotel's room type by name
            hotel_room_type = get_object_or_404(
                HotelRoomType, hotel=event_hotel.hotel, name=room_type_name
            )
            obj = get_object_or_404(
                EventHotelRoomType,
                event_hotel=event_hotel,
                hotel_room_type=hotel_room_type,
            )
            return Response(EventHotelRoomTypeSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching availability", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "put": doc_update(
            request=None,
            response=EventHotelRoomTypeSerializer(many=True),
            description="Bulk update available_count for multiple event-hotel room type allocations",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class BulkRoomAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        updates = request.data.get("room_updates", [])
        if not isinstance(updates, list):
            return Response({"detail": "room_updates should be a list"}, status=400)

        updated = []
        try:
            for upd in updates:
                pk = upd.get("id")
                count = upd.get("available_count")
                if not pk or count is None:
                    continue
                obj = EventHotelRoomType.objects.get(pk=pk)
                # Optional: basic guard to prevent available > allocation
                if count < 0 or count > obj.allocation_count:
                    continue
                obj.available_count = count
                obj.save()
                updated.append(obj)
            return Response(EventHotelRoomTypeSerializer(updated, many=True).data)
        except EventHotelRoomType.DoesNotExist:
            return Response({"detail": "One or more IDs not found."}, status=404)
        except Exception as e:
            return Response(
                {"detail": "Error updating availability", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventHotelRoomTypeSerializer(many=True),
            parameters=[query_param("event", "uuid", True, "Event UUID")],
            description="List all room type allocations for a given Event (across all EventHotels under that event).",
            tags=["Event Hotel Room Types"],
        ),
    }
)
class RoomTypesByEventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        event_id = request.GET.get("event")
        if not event_id:
            return Response({"detail": "Event UUID required"}, status=400)

        try:
            qs = EventHotelRoomType.objects.filter(
                event_hotel__event_id=event_id
            ).select_related(
                "event_hotel",
                "event_hotel__hotel",
                "hotel_room_type",
                "hotel_room_type__hotel",
            )
            data = EventHotelRoomTypeSerializer(qs, many=True).data
            return Response(data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error fetching room type allocations for event",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
