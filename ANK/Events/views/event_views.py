from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import models
from Departments.mixins import DepartmentAccessMixin
from Departments.permissions import PermissionChecker

from Events.models.session_model import Session
from Events.models.session_registration import SessionRegistration
from Guest.serializers import RestrictedGuestSerializer
from Logistics.models.accomodation_models import Accommodation
from Logistics.models.travel_details_models import TravelDetail
from Logistics.serializers.accomodation_serializers import AccommodationSerializer
from Logistics.serializers.travel_details_serializers import TravelDetailSerializer
from Events.serializers.session_serializers import (
    SessionRegistrationSerializer,
    SessionSerializer,
)
from docs.serializers import EventAttendeeSerializer
from Events.models.event_model import Event, EventField
from Events.serializers.event_serializers import (
    EventFieldSerializer,
    EventRegistrationFieldSerializer,
)
from Events.models.event_registration_model import (
    EventRegistration,
    EventRegistrationField,
    ExtraAttendee,
)
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
class EventListCreateView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return Event.objects.all()

    def get(self, request):
        try:
            # Use DepartmentAccessMixin to filter queryset based on user role
            qs = self.get_queryset()
            return Response(EventSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing events", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)
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
class EventDetailView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        """Override to provide base queryset for filtering."""
        return Event.objects.all()

    def get(self, request, pk):
        try:
            # Use get_queryset to ensure user has access
            qs = self.get_queryset()
            ev = get_object_or_404(qs, pk=pk)
            return Response(EventSerializer(ev, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            ev = get_object_or_404(Event, pk=pk)
            ser = EventSerializer(ev, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ev = ser.save()
            return Response(EventSerializer(ev, context=self.get_serializer_context()).data)
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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
class EventRegistrationListCreateView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return EventRegistration.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            return Response(EventRegistrationSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventRegistrationSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(
                EventRegistrationSerializer(reg, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED
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
        "patch": doc_update(
            request=EventRegistrationSerializer,
            response=EventRegistrationSerializer,
            description="Partially update a registration by ID (supports logistics_status updates)",
            tags=["Event Registrations"],
        ),
        "delete": doc_destroy(description="Delete a registration by ID"),
    }
)
class EventRegistrationDetailView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return EventRegistration.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            reg = get_object_or_404(qs, pk=pk)
            return Response(EventRegistrationSerializer(reg, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            ser = EventRegistrationSerializer(reg, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(EventRegistrationSerializer(reg, context=self.get_serializer_context()).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        try:
            reg = get_object_or_404(EventRegistration, pk=pk)
            ser = EventRegistrationSerializer(reg, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(EventRegistrationSerializer(reg, context=self.get_serializer_context()).data)
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
            response=EventRegistrationFieldSerializer(many=True),
            description="List all event registration fields",
            tags=["Event Registration Fields"],
        ),
        "post": doc_create(
            request=EventRegistrationFieldSerializer,
            response=EventRegistrationFieldSerializer,
            description="Create a new event registration field",
            tags=["Event Registration Fields"],
        ),
    }
)
class EventRegistrationFieldList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = EventRegistrationField.objects.all()
            return Response(EventRegistrationFieldSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event registration fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventRegistrationFieldSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event registration field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventRegistrationFieldSerializer,
            description="Retrieve an event registration field by ID",
            tags=["Event Registration Fields"],
        ),
        "put": doc_update(
            request=EventRegistrationFieldSerializer,
            response=EventRegistrationFieldSerializer,
            description="Update an event registration field by ID",
            tags=["Event Registration Fields"],
        ),
        "delete": doc_destroy(
            description="Delete an event registration field by ID",
            tags=["Event Registration Fields"],
        ),
    }
)
class EventRegistrationFieldDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventRegistrationField, pk=pk)
            return Response(EventRegistrationFieldSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event registration field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventRegistrationField, pk=pk)
            ser = EventRegistrationFieldSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event registration field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventRegistrationField, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event registration field", "error": str(e)},
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
class ExtraAttendeeListCreateView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return ExtraAttendee.objects.all()

    def get(self, request):
        try:
            qs = self.get_queryset()
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
class ExtraAttendeeDetailView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return ExtraAttendee.objects.all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            extra = get_object_or_404(qs, pk=pk)
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
class ExtraAttendeesForRegistrationAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return ExtraAttendee.objects.all()

    def get(self, request, pk):
        # Ensure user has access to this registration's event
        accessible_events = PermissionChecker.get_user_accessible_events(request.user)
        reg = get_object_or_404(EventRegistration, pk=pk)
        if not accessible_events.filter(id=reg.event_id).exists() and request.user.role != 'super_admin':
            return Response(
                {"detail": "You don't have access to this event"},
                status=status.HTTP_403_FORBIDDEN
            )
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
class EventSessionsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return Session.objects.all()

    def get(self, request, pk):
        # Ensure user has access to this event
        accessible_events = PermissionChecker.get_user_accessible_events(request.user)
        if not accessible_events.filter(id=pk).exists() and request.user.role != 'super_admin':
            return Response(
                {"detail": "You don't have access to this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        event = get_object_or_404(Event, pk=pk)
        try:
            qs = self.get_queryset().filter(event_id=pk)
            return Response(SessionSerializer(qs, many=True, context=self.get_serializer_context()).data)
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
class EventRegistrationsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return EventRegistration.objects.all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this event
            from Events.models.event_model import Event
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=pk).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(event_id=pk)
            return Response(EventRegistrationSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing event registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


## ------- Views for accommodations and Travel details of ------- ##
# Event-level: list all accommodations for a given event
@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given event",
            tags=["Event Accommodations"],
        )
    }
)
class EventAccommodationsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.accomodation_models import Accommodation
        return Accommodation.objects.all()

    def get(self, request, pk):
        try:
            # Find all registrations and extras for this event
            reg_ids = list(
                EventRegistration.objects.filter(event_id=pk).values_list(
                    "id", flat=True
                )
            )
            extra_ids = list(
                ExtraAttendee.objects.filter(registration__event_id=pk).values_list(
                    "id", flat=True
                )
            )
            # Find accommodations where any are assigned to these participants
            accos = Accommodation.objects.filter(
                models.Q(event__id=pk)
                & (
                    models.Q(event_registrations__id__in=reg_ids)
                    | models.Q(extra_attendees__id__in=extra_ids)
                )
            ).distinct()
            return Response(AccommodationSerializer(accos, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing accommodations for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Event-level: list all travel details for a given event
@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given event",
            tags=["Event Travel Details"],
        )
    }
)
class EventTravelDetailsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.travel_details_models import TravelDetail
        return TravelDetail.objects.all()

    def get(self, request, pk):
        try:
            reg_ids = list(
                EventRegistration.objects.filter(event_id=pk).values_list(
                    "id", flat=True
                )
            )
            extra_ids = list(
                ExtraAttendee.objects.filter(registration__event_id=pk).values_list(
                    "id", flat=True
                )
            )
            travels = TravelDetail.objects.filter(
                models.Q(event__id=pk)
                & (
                    models.Q(event_registrations__id__in=reg_ids)
                    | models.Q(extra_attendees__id__in=extra_ids)
                )
            ).distinct()
            return Response(TravelDetailSerializer(travels, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing travel details for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Registration-level: list all accommodations for an event registration
@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given event registration",
            tags=["Event Registration Accommodations"],
        )
    }
)
class EventRegistrationAccommodationsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.accomodation_models import Accommodation
        return Accommodation.objects.all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this registration's event
            reg = get_object_or_404(EventRegistration, pk=pk)
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=reg.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(event_registrations__id=pk)
            return Response(AccommodationSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing accommodations for registration",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Registration-level: list all travel details for an event registration
@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given event registration",
            tags=["Event Registration Travel Details"],
        )
    }
)
class EventRegistrationTravelDetailsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.travel_details_models import TravelDetail
        return TravelDetail.objects.all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this registration's event
            reg = get_object_or_404(EventRegistration, pk=pk)
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=reg.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(event_registrations__id=pk)
            return Response(TravelDetailSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing travel details for registration",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Attendee-level: list all accommodations for an extra attendee
@document_api_view(
    {
        "get": doc_list(
            response=AccommodationSerializer(many=True),
            description="List all accommodations for a given extra attendee",
            tags=["Extra Attendee Accommodations"],
        )
    }
)
class ExtraAttendeeAccommodationsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.accomodation_models import Accommodation
        return Accommodation.objects.all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this extra attendee's event
            extra = get_object_or_404(ExtraAttendee, pk=pk)
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=extra.registration.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(extra_attendees__id=pk)
            return Response(AccommodationSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing accommodations for extra attendee",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Attendee-level: list all travel details for an extra attendee
@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailSerializer(many=True),
            description="List all travel details for a given extra attendee",
            tags=["Extra Attendee Travel Details"],
        )
    }
)
class ExtraAttendeeTravelDetailsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        from Logistics.models.travel_details_models import TravelDetail
        return TravelDetail.objects.all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this extra attendee's event
            extra = get_object_or_404(ExtraAttendee, pk=pk)
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=extra.registration.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(extra_attendees__id=pk)
            return Response(TravelDetailSerializer(qs, many=True, context=self.get_serializer_context()).data)
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
class EventAllAttendeesAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /events/{event_pk}/all-attendees/
    Returns a list of all EventRegistrations (with Guest data)
    and their ExtraAttendees for that event.
    """

    def get(self, request, event_pk):
        try:
            # Ensure user has access to this event
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=event_pk).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
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
class EventRegistrationAttendeesAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /event-registrations/{registration_pk}/attendees/
    Returns guest info + extra_attendees for this event registration.
    """

    def get(self, request, registration_pk):
        try:
            # Ensure user has access to this registration's event
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            reg = get_object_or_404(EventRegistration, pk=registration_pk)
            if not accessible_events.filter(id=reg.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
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


@document_api_view(
    {
        "get": doc_list(
            response=SessionRegistrationSerializer(many=True),
            description=(
                "List all session registrations for the guest referenced by the EventRegistration. "
                "Returns all SessionRegistrations for sessions under the same event for this guest."
            ),
            tags=["Event Registrations"],
        ),
    }
)
class EventRegistrationSessionRegistrationsAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /api/event-registrations/{registration_id}/session-registrations/
    Returns all session registrations for the guest in this event registration.
    """

    def get(self, request, registration_id):
        try:
            # Ensure user has access to this registration's event
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            # 1. Get the EventRegistration (404s if not found)
            event_reg = get_object_or_404(EventRegistration, pk=registration_id)
            if not accessible_events.filter(id=event_reg.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            guest = event_reg.guest

            # 2. Get all SessionRegistrations for this guest in this event
            session_regs = SessionRegistration.objects.filter(
                guest=guest, session__event=event_reg.event
            ).select_related("session")

            # 3. Serialize the session registrations and their sessions
            session_data = [SessionSerializer(sr.session).data for sr in session_regs]
            session_reg_data = SessionRegistrationSerializer(
                session_regs, many=True
            ).data

            return Response(
                {
                    "sessions": session_data,  # Only sessions this guest is registered for
                    "session_registrations": session_reg_data,
                },
                status=status.HTTP_200_OK,
            )
        except EventRegistration.DoesNotExist:
            return Response(
                {"detail": "EventRegistration not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"detail": "Error fetching session registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

