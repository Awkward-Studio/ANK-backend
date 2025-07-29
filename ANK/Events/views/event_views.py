from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from Guest.serializers import RestrictedGuestSerializer
from Logistics.models.accomodation_models import Accommodation
from Logistics.models.travel_details_models import TravelDetail
from Logistics.serializers.accomodation_serializers import AccommodationSerializer
from Logistics.serializers.travel_details_serializers import TravelDetailSerializer
from Events.serializers.session_serializers import SessionSerializer
from docs.serializers import EventAttendeeSerializer
from Events.models.event_model import Event, EventField
from Events.serializers.event_serializers import EventFieldSerializer
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
            response=EventFieldSerializer(many=True),
            description="List all event fields",
            tags=["Event Fields"],
        ),
        "post": doc_create(
            request=EventFieldSerializer,
            response=EventFieldSerializer,
            description="Create a new event field",
            tags=["Event Fields"],
        ),
    }
)
class EventFieldList(APIView):
    def get(self, request):
        try:
            qs = EventField.objects.all()
            return Response(EventFieldSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventFieldSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventFieldSerializer,
            description="Retrieve an event field by ID",
            tags=["Event Fields"],
        ),
        "put": doc_update(
            request=EventFieldSerializer,
            response=EventFieldSerializer,
            description="Update an event field by ID",
            tags=["Event Fields"],
        ),
        "delete": doc_destroy(
            description="Delete an event field by ID", tags=["Event Fields"]
        ),
    }
)
class EventFieldDetail(APIView):
    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventField, pk=pk)
            return Response(EventFieldSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventField, pk=pk)
            ser = EventFieldSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventField, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event field", "error": str(e)},
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


@document_api_view(
    {
        "get": doc_list(
            response=ExtraAttendeeSerializer(many=True),
            description="List all extra attendees for a given event registration",
            tags=["Extra Attendees"],
        )
    }
)
class ExtraAttendeesForRegistrationAPIView(APIView):
    def get(self, request, pk):
        reg = get_object_or_404(EventRegistration, pk=pk)
        try:
            extras = reg.extra_attendees.all()
            return Response(ExtraAttendeeSerializer(extras, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing extra attendees", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=SessionSerializer(many=True),
            description="List all sessions for a given event",
            tags=["Event Sessions"],
        )
    }
)
class EventSessionsAPIView(APIView):
    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        try:
            sessions = event.sessions.all()
            return Response(SessionSerializer(sessions, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing event sessions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventRegistrationSerializer(many=True),
            description="List all registrations for a given event",
            tags=["Event Registrations"],
        )
    }
)
class EventRegistrationsAPIView(APIView):
    def get(self, request, pk):
        try:
            regs = EventRegistration.objects.filter(event_id=pk)
            return Response(EventRegistrationSerializer(regs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing event registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


## ------- Views for accommodations and Travel details of ------- ##
@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given event",
            tags=["Event Accommodations"],
        )
    }
)
class EventAccommodationsAPIView(APIView):
    def get(self, request, pk):
        try:
            reg_ids = EventRegistration.objects.filter(event_id=pk).values_list(
                "id", flat=True
            )
            accos = Accommodation.objects.filter(event_registration_id__in=reg_ids)
            return Response(AccommodationSerializer(accos, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing accommodations for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given event",
            tags=["Event Travel Details"],
        )
    }
)
class EventTravelDetailsAPIView(APIView):
    def get(self, request, pk):
        try:
            reg_ids = EventRegistration.objects.filter(event_id=pk).values_list(
                "id", flat=True
            )
            travels = TravelDetail.objects.filter(event_registration_id__in=reg_ids)
            return Response(TravelDetailSerializer(travels, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing travel details for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given event registration",
            tags=["Event Registration Accommodations"],
        )
    }
)
class EventRegistrationAccommodationsAPIView(APIView):
    def get(self, request, pk):
        try:
            accos = Accommodation.objects.filter(event_registration_id=pk)
            return Response(AccommodationSerializer(accos, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing accommodations for registration",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given event registration",
            tags=["Event Registration Travel Details"],
        )
    }
)
class EventRegistrationTravelDetailsAPIView(APIView):
    def get(self, request, pk):
        try:
            travels = TravelDetail.objects.filter(event_registration_id=pk)
            return Response(TravelDetailSerializer(travels, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing travel details for registration",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given extra attendee",
            tags=["Extra Attendee Accommodations"],
        )
    }
)
class ExtraAttendeeAccommodationsAPIView(APIView):
    def get(self, request, pk):
        try:
            accos = Accommodation.objects.filter(attendee_id=pk)
            return Response(AccommodationSerializer(accos, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing accommodations for extra attendee",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given extra attendee",
            tags=["Extra Attendee Travel Details"],
        )
    }
)
class ExtraAttendeeTravelDetailsAPIView(APIView):
    def get(self, request, pk):
        try:
            travels = TravelDetail.objects.filter(attendee_id=pk)
            return Response(TravelDetailSerializer(travels, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing travel details for extra attendee",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


## ------ Fetching guest_data from a certain object ------- ##
@document_api_view(
    {
        "get": doc_list(
            response=EventAttendeeSerializer(many=True),
            description="List all registrations and extra attendees for an event",
            tags=["Event Attendees"],
        )
    }
)
class EventAllAttendeesAPIView(APIView):
    """
    GET /events/{event_pk}/all-attendees/
    Returns a list of all EventRegistrations (with Guest data)
    and their ExtraAttendees for that event.
    """

    def get(self, request, event_pk):
        try:
            # Ensure event exists
            get_object_or_404(Event, pk=event_pk)
            # Get all EventRegistrations for this event (prefetch extras for efficiency)
            registrations = (
                EventRegistration.objects.filter(event_id=event_pk)
                .select_related("guest")
                .prefetch_related("extra_attendees")
            )

            results = []
            for reg in registrations:
                guest = reg.guest
                guest_data = {
                    "id": str(guest.id),
                    "name": guest.name,
                    "phone": guest.phone,
                    "email": guest.email,
                    "city": guest.city,
                }
                extras = [
                    {
                        "extra_attendee_id": str(extra.id),
                        "name": extra.name,
                        "phone": extra.phone,
                    }
                    for extra in reg.extra_attendees.all()
                ]
                results.append(
                    {
                        "event_registration_id": str(reg.id),
                        "guest": guest_data,
                        "extras": extras,
                    }
                )
            return Response(results)
        except Exception as e:
            return Response(
                {"detail": "Error fetching attendees", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            description="Get guest and extra_attendees for an event registration",
            tags=["Event Registration Attendees"],
        )
    }
)
class EventRegistrationAttendeesAPIView(APIView):
    """
    GET /event-registrations/{registration_pk}/attendees/
    Returns guest info + extra_attendees for this event registration.
    """

    def get(self, request, registration_pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=registration_pk)
            guest_data = RestrictedGuestSerializer(reg.guest).data
            extras = [
                {
                    "extra_attendee_id": str(extra.id),
                    "name": extra.name,
                    "phone": extra.phone,
                    "photo_id": extra.photo_id.url if extra.photo_id else None,
                }
                for extra in reg.extra_attendees.all()
            ]
            result = {
                "event_registration_id": str(reg.id),
                "guest": guest_data,
                "extras": extras,
            }
            return Response(result)
        except Exception as e:
            return Response(
                {"detail": "Error fetching attendees", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
