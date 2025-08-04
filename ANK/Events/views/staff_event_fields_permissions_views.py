from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.shortcuts import get_object_or_404

from Staff.models import User
from Events.models.event_model import Event, EventField
from Guest.models import GuestField
from Events.models.session_model import SessionField
from Events.models.staff_event_field_permissions import (
    UserEventFieldPermission,
    UserEventGuestFieldPermission,
    UserEventSessionFieldPermission,
)
from Events.serializers.staff_event_field_permission_serializers import (
    EventFieldPermissionSerializer,
    GuestFieldPermissionSerializer,
    SessionFieldPermissionSerializer,
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


@document_api_view(
    {
        "post": doc_create(
            request=None,  # customize as needed
            response=None,  # customize as needed
            description="Bulk assign all field permissions (event/guest/session) for a user on an event. Wipes previous.",
            tags=["Field Permissions"],
        )
    }
)
class UserEventAssignAllFieldPermsAPIView(APIView):
    """
    POST /events/{event_pk}/users/{user_pk}/set-all-field-perms/
    {
      "eventfield_ids": [ ... ],
      "guestfield_ids": [ ... ],
      "sessionfield_ids": [ ... ]
    }
    """

    def post(self, request, event_pk, user_pk):
        try:
            event = get_object_or_404(Event, pk=event_pk)
            user = get_object_or_404(User, pk=user_pk)

            eventfield_ids = request.data.get("eventfield_ids", [])
            guestfield_ids = request.data.get("guestfield_ids", [])
            sessionfield_ids = request.data.get("sessionfield_ids", [])

            # Validate all are lists
            if not all(
                isinstance(ids, list)
                for ids in [eventfield_ids, guestfield_ids, sessionfield_ids]
            ):
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
                },
            },
            description="List all allowed event, guest, and session fields for a user on a given event.",
            tags=["Field Permissions"],
        )
    }
)
class UserEventAllAllowedFieldsAPIView(APIView):
    """
    GET /events/<event_pk>/users/<user_pk>/allowed-fields/
    Returns all allowed event fields, guest fields, and session fields for this user on this event.
    """

    def get(self, request, event_pk, user_pk):
        user = get_object_or_404(User, pk=user_pk)
        event = get_object_or_404(Event, pk=event_pk)
        try:
            # Get all allowed event fields
            event_perms = UserEventFieldPermission.objects.filter(
                user=user, event=event
            ).select_related("event_field")
            event_fields = [
                {
                    "id": perm.event_field.id,
                    "name": perm.event_field.name,
                    "label": perm.event_field.label,
                }
                for perm in event_perms
            ]

            # Get all allowed guest fields
            guest_perms = UserEventGuestFieldPermission.objects.filter(
                user=user, event=event
            ).select_related("guest_field")
            guest_fields = [
                {
                    "id": perm.guest_field.id,
                    "name": perm.guest_field.name,
                    "label": perm.guest_field.label,
                }
                for perm in guest_perms
            ]

            # Get all allowed session fields
            session_perms = UserEventSessionFieldPermission.objects.filter(
                user=user, event=event
            ).select_related("session_field")
            session_fields = [
                {
                    "id": perm.session_field.id,
                    "name": perm.session_field.name,
                    "label": perm.session_field.label,
                }
                for perm in session_perms
            ]

            return Response(
                {
                    "event_fields": event_fields,
                    "guest_fields": guest_fields,
                    "session_fields": session_fields,
                }
            )
        except Exception as e:
            return Response(
                {"detail": "Failed to fetch allowed fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
