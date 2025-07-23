from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from Events.models.event_model import Event
from Events.models.event_registration_model import EventRegistration, ExtraAttendee
from Events.serializers.event_serializers import (
    EventSerializer,
    EventRegistrationSerializer,
    ExtraAttendeeSerializer,
)

from utils.swagger import (
    doc_create,
    doc_list,
    doc_retrieve,
    doc_update,
    doc_destroy,
    document_api_view,
    query_param,
)


@document_api_view(
    {
        "get": doc_list(
            response=EventSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by event name (contains)"),
                query_param(
                    "start_date", "date", False, "Filter events starting on or after"
                ),
                query_param(
                    "end_date", "date", False, "Filter events ending on or before"
                ),
            ],
            description="List all events, optionally filtered",
            tags=["Events"],
        ),
        "post": doc_create(
            request=EventSerializer,
            response=EventSerializer,
            description="Create a new event",
            tags=["Events"],
        ),
    }
)
class EventListCreateView(APIView):
    def get(self, request):
        try:
            qs = Event.objects.all()
            return Response(EventSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing events", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventSerializer,
            description="Retrieve an event by ID",
            tags=["Events"],
        ),
        "put": doc_update(
            request=EventSerializer,
            response=EventSerializer,
            description="Update an event by ID",
            tags=["Events"],
        ),
        "delete": doc_destroy(description="Delete an event by ID", tags=["Events"]),
    }
)
class EventDetailView(APIView):
    def get(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            return Response(EventSerializer(ev).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            ser = EventSerializer(ev, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            ev.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventRegistrationSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("guest", "uuid", False, "Filter by guest ID"),
                query_param("rsvp_status", "str", False, "Filter by RSVP status"),
            ],
            description="List all event registrations",
            tags=["Event Registrations"],
        ),
        "post": doc_create(
            request=EventRegistrationSerializer,
            response=EventRegistrationSerializer,
            description="Register a guest to an event",
            tags=["Event Registrations"],
        ),
    }
)
class EventRegistrationListCreateView(APIView):
    def get(self, request):
        try:
            qs = EventRegistration.objects.all()
            return Response(EventRegistrationSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventRegistrationSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(
                EventRegistrationSerializer(reg).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventRegistrationSerializer,
            description="Retrieve a registration by ID",
            tags=["Event Registrations"],
        ),
        "put": doc_update(
            request=EventRegistrationSerializer,
            response=EventRegistrationSerializer,
            description="Update a registration by ID",
            tags=["Event Registrations"],
        ),
        "delete": doc_destroy(description="Delete a registration by ID"),
    }
)
class EventRegistrationDetailView(APIView):
    def get(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            return Response(EventRegistrationSerializer(reg).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            ser = EventRegistrationSerializer(reg, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(EventRegistrationSerializer(reg).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            reg.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=ExtraAttendeeSerializer(many=True),
            parameters=[
                query_param("registration", "uuid", False, "Filter by registration ID"),
                query_param("name", "str", False, "Filter by attendee name"),
            ],
            description="List all extra attendees",
            tags=["Extra Attendees"],
        ),
        "post": doc_create(
            request=ExtraAttendeeSerializer,
            response=ExtraAttendeeSerializer,
            description="Create a new extra attendee",
            tags=["Extra Attendees"],
        ),
    }
)
class ExtraAttendeeListCreateView(APIView):
    def get(self, request):
        try:
            qs = ExtraAttendee.objects.all()
            return Response(ExtraAttendeeSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching extra attendees", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = ExtraAttendeeSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            extra = ser.save()
            return Response(
                ExtraAttendeeSerializer(extra).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating extra attendee", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=ExtraAttendeeSerializer,
            description="Retrieve an extra attendee by ID",
            tags=["Extra Attendees"],
        ),
        "put": doc_update(
            request=ExtraAttendeeSerializer,
            response=ExtraAttendeeSerializer,
            description="Update an extra attendee by ID",
            tags=["Extra Attendees"],
        ),
        "delete": doc_destroy(
            description="Delete an extra attendee by ID",
            tags=["Extra Attendees"],
        ),
    }
)
class ExtraAttendeeDetailView(APIView):
    def get(self, request, pk):
        try:
            extra = get_object_or_404(ExtraAttendee, pk=pk)
            return Response(ExtraAttendeeSerializer(extra).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching extra attendee", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            extra = get_object_or_404(ExtraAttendee, pk=pk)
            ser = ExtraAttendeeSerializer(extra, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            return Response(ExtraAttendeeSerializer(updated).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating extra attendee", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            extra = get_object_or_404(ExtraAttendee, pk=pk)
            extra.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting extra attendee", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
