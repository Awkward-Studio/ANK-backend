from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from Events.models.event_registration_model import EventRegistrationField
from Logistics.models.accomodation_models import AccommodationField
from Logistics.models.travel_details_models import TravelDetailField
from Staff.models import User
from Events.models.event_model import Event, EventField
from Guest.models import GuestField
from Events.models.session_model import SessionField
from Events.models.staff_event_field_permissions import (
    UserEventAccommodationFieldPermission,
    UserEventEventRegistrationFieldPermission,
    UserEventFieldPermission,
    UserEventGuestFieldPermission,
    UserEventSessionFieldPermission,
    UserEventTravelDetailFieldPermission,
)
from Events.serializers.staff_event_field_permission_serializers import (
    AccommodationFieldPermissionSerializer,
    EventFieldPermissionSerializer,
    EventRegistrationFieldPermissionSerializer,
    GuestFieldPermissionSerializer,
    SessionFieldPermissionSerializer,
    TravelDetailFieldPermissionSerializer,
)

from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_update,
    doc_destroy,
    query_param,
)

# ─── EventField permissions ────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=EventFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed EventFields for a given event",
            tags=["Event Field Permissions"],
        ),
        "put": doc_update(
            request=EventFieldPermissionSerializer(many=True),
            response=EventFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed EventFields for a given event",
            tags=["Event Field Permissions"],
        ),
    }
)
class UserEventEventFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("event_field")
            return Response(EventFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing event‐field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            ids = request.data.get("eventfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "eventfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            UserEventFieldPermission.objects.filter(user=user, event=event).delete()
            for eid in ids:
                ef = get_object_or_404(EventField, pk=eid)
                UserEventFieldPermission.objects.get_or_create(
                    user=user, event=event, event_field=ef
                )
            perms = UserEventFieldPermission.objects.filter(user=user, event=event)
            return Response(EventFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error replacing event‐field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=EventFieldPermissionSerializer,
            response=EventFieldPermissionSerializer(many=True),
            description="Add a single EventField permission for a user on an event",
            tags=["Event Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single EventField permission for a user on an event",
            tags=["Event Field Permissions"],
        ),
    }
)
class UserEventEventFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            eid = request.data.get("eventfield_id")
            if not eid:
                return Response(
                    {"detail": "eventfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            ef = get_object_or_404(EventField, pk=eid)
            UserEventFieldPermission.objects.get_or_create(
                user=user, event=event, event_field=ef
            )
            perms = UserEventFieldPermission.objects.filter(user=user, event=event)
            return Response(EventFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error adding event‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            ef = get_object_or_404(EventField, pk=field_pk)
            UserEventFieldPermission.objects.filter(
                user=user, event=event, event_field=ef
            ).delete()
            perms = UserEventFieldPermission.objects.filter(user=user, event=event)
            return Response(EventFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error removing event‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── GuestField permissions ────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=GuestFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed GuestFields for a given event",
            tags=["Guest Field Permissions"],
        ),
        "put": doc_update(
            request=GuestFieldPermissionSerializer(many=True),
            response=GuestFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed GuestFields for a given event",
            tags=["Guest Field Permissions"],
        ),
    }
)
class UserEventGuestFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventGuestFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("guest_field")
            return Response(GuestFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing guest‐field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            ids = request.data.get("guestfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "guestfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            UserEventGuestFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            for gid in ids:
                gf = get_object_or_404(GuestField, pk=gid)
                UserEventGuestFieldPermission.objects.get_or_create(
                    user=user, event=event, guest_field=gf
                )
            perms = UserEventGuestFieldPermission.objects.filter(user=user, event=event)
            return Response(GuestFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error replacing guest‐field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=GuestFieldPermissionSerializer,
            response=GuestFieldPermissionSerializer(many=True),
            description="Add a single GuestField permission for a user on an event",
            tags=["Guest Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single GuestField permission for a user on an event",
            tags=["Guest Field Permissions"],
        ),
    }
)
class UserEventGuestFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            gid = request.data.get("guestfield_id")
            if not gid:
                return Response(
                    {"detail": "guestfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            gf = get_object_or_404(GuestField, pk=gid)
            UserEventGuestFieldPermission.objects.get_or_create(
                user=user, event=event, guest_field=gf
            )
            perms = UserEventGuestFieldPermission.objects.filter(user=user, event=event)
            return Response(GuestFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error adding guest‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            gf = get_object_or_404(GuestField, pk=field_pk)
            UserEventGuestFieldPermission.objects.filter(
                user=user, event=event, guest_field=gf
            ).delete()
            perms = UserEventGuestFieldPermission.objects.filter(user=user, event=event)
            return Response(GuestFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error removing guest‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── SessionField permissions ──────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=SessionFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed SessionFields for a given event",
            tags=["Session Field Permissions"],
        ),
        "put": doc_update(
            request=SessionFieldPermissionSerializer(many=True),
            response=SessionFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed SessionFields for a given event",
            tags=["Session Field Permissions"],
        ),
    }
)
class UserEventSessionFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventSessionFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("session_field")
            return Response(SessionFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing session‐field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            ids = request.data.get("sessionfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "sessionfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            for sid in ids:
                sf = get_object_or_404(SessionField, pk=sid)
                UserEventSessionFieldPermission.objects.get_or_create(
                    user=user, event=event, session_field=sf
                )
            perms = UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(SessionFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error replacing session‐field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=SessionFieldPermissionSerializer,
            response=SessionFieldPermissionSerializer(many=True),
            description="Add a single SessionField permission for a user on an event",
            tags=["Session Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single SessionField permission for a user on an event",
            tags=["Session Field Permissions"],
        ),
    }
)
class UserEventSessionFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            sid = request.data.get("sessionfield_id")
            if not sid:
                return Response(
                    {"detail": "sessionfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            sf = get_object_or_404(SessionField, pk=sid)
            UserEventSessionFieldPermission.objects.get_or_create(
                user=user, event=event, session_field=sf
            )
            perms = UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(SessionFieldPermissionSerializer(perms, many=True).data)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error adding session‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            sf = get_object_or_404(SessionField, pk=field_pk)
            UserEventSessionFieldPermission.objects.filter(
                user=user, event=event, session_field=sf
            ).delete()
            perms = UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(SessionFieldPermissionSerializer(perms, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error removing session‐field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -- List/Replace all permissions for a user/event --
@document_api_view(
    {
        "get": doc_list(
            response=TravelDetailFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed TravelDetailFields for a given event",
            tags=["Travel Detail Field Permissions"],
        ),
        "put": doc_update(
            request=TravelDetailFieldPermissionSerializer(many=True),
            response=TravelDetailFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed TravelDetailFields for a given event",
            tags=["Travel Detail Field Permissions"],
        ),
    }
)
class UserEventTravelDetailFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventTravelDetailFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("traveldetail_field")
            return Response(
                TravelDetailFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing travel detail field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            ids = request.data.get("traveldetailfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "traveldetailfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            for tid in ids:
                tf = get_object_or_404(TravelDetailField, pk=tid)
                UserEventTravelDetailFieldPermission.objects.get_or_create(
                    user=user, event=event, traveldetail_field=tf
                )
            perms = UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                TravelDetailFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error replacing travel detail field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -- Add/Remove a single permission --
@document_api_view(
    {
        "post": doc_create(
            request=TravelDetailFieldPermissionSerializer,
            response=TravelDetailFieldPermissionSerializer(many=True),
            description="Add a single TravelDetailField permission for a user on an event",
            tags=["Travel Detail Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single TravelDetailField permission for a user on an event",
            tags=["Travel Detail Field Permissions"],
        ),
    }
)
class UserEventTravelDetailFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            tid = request.data.get("traveldetailfield_id")
            if not tid:
                return Response(
                    {"detail": "traveldetailfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            tf = get_object_or_404(TravelDetailField, pk=tid)
            UserEventTravelDetailFieldPermission.objects.get_or_create(
                user=user, event=event, traveldetail_field=tf
            )
            perms = UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                TravelDetailFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error adding travel detail field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            tf = get_object_or_404(TravelDetailField, pk=field_pk)
            UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event, traveldetail_field=tf
            ).delete()
            perms = UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                TravelDetailFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error removing travel detail field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventRegistrationFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed EventRegistrationFields for a given event",
            tags=["Event Registration Field Permissions"],
        ),
        "put": doc_update(
            request=EventRegistrationFieldPermissionSerializer(many=True),
            response=EventRegistrationFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed EventRegistrationFields for a given event",
            tags=["Event Registration Field Permissions"],
        ),
    }
)
class UserEventEventRegistrationFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventEventRegistrationFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("eventregistration_field")
            return Response(
                EventRegistrationFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing event registration field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            ids = request.data.get("eventregistrationfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "eventregistrationfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            for eid in ids:
                ef = get_object_or_404(EventRegistrationField, pk=eid)
                UserEventEventRegistrationFieldPermission.objects.get_or_create(
                    user=user, event=event, eventregistration_field=ef
                )
            perms = UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                EventRegistrationFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error replacing event registration field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=EventRegistrationFieldPermissionSerializer,
            response=EventRegistrationFieldPermissionSerializer(many=True),
            description="Add a single EventRegistrationField permission for a user on an event",
            tags=["Event Registration Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single EventRegistrationField permission for a user on an event",
            tags=["Event Registration Field Permissions"],
        ),
    }
)
class UserEventEventRegistrationFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            eid = request.data.get("eventregistrationfield_id")
            if not eid:
                return Response(
                    {"detail": "eventregistrationfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            ef = get_object_or_404(EventRegistrationField, pk=eid)
            UserEventEventRegistrationFieldPermission.objects.get_or_create(
                user=user, event=event, eventregistration_field=ef
            )
            perms = UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                EventRegistrationFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error adding event registration field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            ef = get_object_or_404(EventRegistrationField, pk=field_pk)
            UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event, eventregistration_field=ef
            ).delete()
            perms = UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                EventRegistrationFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error removing event registration field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=AccommodationFieldPermissionSerializer(many=True),
            parameters=[
                query_param("event_pk", "uuid", True, "Event ID"),
                query_param("user_pk", "uuid", True, "User ID"),
            ],
            description="List or filter a user’s allowed AccommodationFields for a given event",
            tags=["Accommodation Field Permissions"],
        ),
        "put": doc_update(
            request=AccommodationFieldPermissionSerializer(many=True),
            response=AccommodationFieldPermissionSerializer(many=True),
            description="Replace a user’s allowed AccommodationFields for a given event",
            tags=["Accommodation Field Permissions"],
        ),
    }
)
class UserEventAccommodationFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_pk, user_pk):
        try:
            perms = UserEventAccommodationFieldPermission.objects.filter(
                event__pk=event_pk, user__pk=user_pk
            ).select_related("accommodation_field")
            return Response(
                AccommodationFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing accommodation field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, event_pk, user_pk):
        try:
            ids = request.data.get("accommodationfield_ids", [])
            if not isinstance(ids, list):
                return Response(
                    {"detail": "accommodationfield_ids must be a list of UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            for aid in ids:
                af = get_object_or_404(AccommodationField, pk=aid)
                UserEventAccommodationFieldPermission.objects.get_or_create(
                    user=user, event=event, accommodation_field=af
                )
            perms = UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                AccommodationFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error replacing accommodation field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=AccommodationFieldPermissionSerializer,
            response=AccommodationFieldPermissionSerializer(many=True),
            description="Add a single AccommodationField permission for a user on an event",
            tags=["Accommodation Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Remove a single AccommodationField permission for a user on an event",
            tags=["Accommodation Field Permissions"],
        ),
    }
)
class UserEventAccommodationFieldPermAddRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_pk, user_pk):
        try:
            aid = request.data.get("accommodationfield_id")
            if not aid:
                return Response(
                    {"detail": "accommodationfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            af = get_object_or_404(AccommodationField, pk=aid)
            UserEventAccommodationFieldPermission.objects.get_or_create(
                user=user, event=event, accommodation_field=af
            )
            perms = UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                AccommodationFieldPermissionSerializer(perms, many=True).data
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "detail": "Error adding accommodation field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, event_pk, user_pk, field_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            event = get_object_or_404(Event, pk=event_pk)
            af = get_object_or_404(AccommodationField, pk=field_pk)
            UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event, accommodation_field=af
            ).delete()
            perms = UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event
            )
            return Response(
                AccommodationFieldPermissionSerializer(perms, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error removing accommodation field permission",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=None,  # customize as needed
            response=None,  # customize as needed
            description="Bulk assign all field permissions (event/guest/session/travel/accommodation/eventregistration) for a user on an event. Wipes previous.",
            tags=["Field Permissions"],
        )
    }
)
class UserEventAssignAllFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    POST /events/{event_pk}/users/{user_pk}/set-all-field-perms/
    {
      "eventfield_ids": [ ... ],
      "guestfield_ids": [ ... ],
      "sessionfield_ids": [ ... ],
      "traveldetailfield_ids": [ ... ],
      "accommodationfield_ids": [ ... ],
      "eventregistrationfield_ids": [ ... ]
    }
    """

    def post(self, request, event_pk, user_pk):
        try:
            event = get_object_or_404(Event, pk=event_pk)
            user = get_object_or_404(User, pk=user_pk)

            eventfield_ids = request.data.get("eventfield_ids", [])
            guestfield_ids = request.data.get("guestfield_ids", [])
            sessionfield_ids = request.data.get("sessionfield_ids", [])
            traveldetailfield_ids = request.data.get("traveldetailfield_ids", [])
            accommodationfield_ids = request.data.get("accommodationfield_ids", [])
            eventregistrationfield_ids = request.data.get(
                "eventregistrationfield_ids", []
            )

            # Validate all are lists
            all_fields = [
                eventfield_ids,
                guestfield_ids,
                sessionfield_ids,
                traveldetailfield_ids,
                accommodationfield_ids,
                eventregistrationfield_ids,
            ]
            if not all(isinstance(ids, list) for ids in all_fields):
                return Response(
                    {"detail": "All fields must be lists of UUIDs."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Clear all previous perms for this user+event
            UserEventFieldPermission.objects.filter(user=user, event=event).delete()
            UserEventGuestFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            UserEventTravelDetailFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            UserEventAccommodationFieldPermission.objects.filter(
                user=user, event=event
            ).delete()
            UserEventEventRegistrationFieldPermission.objects.filter(
                user=user, event=event
            ).delete()

            # Bulk create EventField perms
            for eid in eventfield_ids:
                ef = get_object_or_404(EventField, pk=eid)
                UserEventFieldPermission.objects.get_or_create(
                    user=user, event=event, event_field=ef
                )

            # Bulk create GuestField perms
            for gid in guestfield_ids:
                gf = get_object_or_404(GuestField, pk=gid)
                UserEventGuestFieldPermission.objects.get_or_create(
                    user=user, event=event, guest_field=gf
                )

            # Bulk create SessionField perms
            for sid in sessionfield_ids:
                sf = get_object_or_404(SessionField, pk=sid)
                UserEventSessionFieldPermission.objects.get_or_create(
                    user=user, event=event, session_field=sf
                )

            # Bulk create TravelDetailField perms
            for tid in traveldetailfield_ids:
                tf = get_object_or_404(TravelDetailField, pk=tid)
                UserEventTravelDetailFieldPermission.objects.get_or_create(
                    user=user, event=event, traveldetail_field=tf
                )

            # Bulk create AccommodationField perms
            for aid in accommodationfield_ids:
                af = get_object_or_404(AccommodationField, pk=aid)
                UserEventAccommodationFieldPermission.objects.get_or_create(
                    user=user, event=event, accommodation_field=af
                )

            # Bulk create EventRegistrationField perms
            for erid in eventregistrationfield_ids:
                erf = get_object_or_404(EventRegistrationField, pk=erid)
                UserEventEventRegistrationFieldPermission.objects.get_or_create(
                    user=user, event=event, eventregistration_field=erf
                )

            return Response(
                {"detail": "All field permissions updated."}, status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"detail": "Error setting all field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response={
                "type": "object",
                "properties": {
                    "event_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                    "guest_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                    "session_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                    "traveldetail_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                    "accommodation_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                    "eventregistration_fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                },
            },
            description="List all allowed event, guest, session, travel detail, accommodation, and event registration fields for a user on a given event.",
            tags=["Field Permissions"],
        )
    }
)
class UserEventAllAllowedFieldsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /events/<event_pk>/users/<user_pk>/allowed-fields/
    Returns all allowed event fields, guest fields, session fields, travel detail fields,
    accommodation fields, and event registration fields for this user on this event.
    """

    def get(self, request, event_pk, user_pk):
        user = get_object_or_404(User, pk=user_pk)
        event = get_object_or_404(Event, pk=event_pk)
        
        try:
            from Departments.permissions import PermissionChecker
            from django.contrib.contenttypes.models import ContentType
            
            # Helper to map model names to response keys
            model_map = {
                'event': 'event_fields',
                'guest': 'guest_fields',
                'session': 'session_fields',
                'traveldetail': 'traveldetail_fields',
                'accommodation': 'accommodation_fields',
                'eventregistration': 'eventregistration_fields',
            }
            
            response_data = {key: [] for key in model_map.values()}
            response_data['model_access'] = {}
            
            from Departments.models import ModelPermission, EventDepartment, DepartmentModelAccess
            
            # Find all event departments the user is assigned to for this event
            event_depts = EventDepartment.objects.filter(
                event=event,
                staff_assignments__user=user
            )
            
            # Calculate aggregate model access across all assigned departments
            assigned_depts = [ed.department for ed in event_depts]
            
            for model_name, response_key in model_map.items():
                try:
                    content_type = ContentType.objects.get(app_label__in=['Events', 'Guest', 'Logistics', 'Departments'], model=model_name)
                    
                    # 1. Aggregate Model CRUD access
                    dept_access = DepartmentModelAccess.objects.filter(
                        department__in=assigned_depts,
                        content_type=content_type
                    )
                    
                    access = {
                        "can_read": any(da.can_read for da in dept_access),
                        "can_write": any(da.can_write for da in dept_access),
                        "can_create": any(da.can_create for da in dept_access),
                        "can_delete": any(da.can_delete for da in dept_access),
                    }
                    
                    # Special Case: Super admin bypass
                    if user.role == 'super_admin':
                        access = {k: True for k in access}
                        
                    response_data['model_access'][model_name] = access

                    # 2. Fetch Field-level permissions
                    perms = ModelPermission.objects.filter(
                        user=user,
                        event_department__in=event_depts,
                        content_type=content_type
                    ).select_related('event_department')
                    
                    for perm in perms:
                        response_data[response_key].append({
                            "id": str(perm.id),
                            "name": perm.field_name,
                            "label": perm.field_name.replace('_', ' ').title(), # Fallback label
                            "permission_type": perm.permission_type,
                        })
                except ContentType.DoesNotExist:
                    continue

            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": "Failed to fetch allowed fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
