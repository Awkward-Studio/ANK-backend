from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from Guest.serializers import RestrictedGuestSerializer
from Events.models.session_model import Session, SessionField
from Events.serializers.session_serializers import SessionFieldSerializer
from Events.models.session_registration import SessionRegistration
from Events.serializers.session_serializers import (
    SessionSerializer,
    SessionRegistrationSerializer,
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
            response=SessionSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("date", "date", False, "Filter by session date"),
            ],
            description="List all sessions",
            tags=["Sessions"],
        ),
        "post": doc_create(
            request=SessionSerializer,
            response=SessionSerializer,
            description="Create a new session",
            tags=["Sessions"],
        ),
    }
)
class SessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Session.objects.all()
            return Response(SessionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing sessions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = SessionSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            sess = ser.save()
            return Response(
                SessionSerializer(sess).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating session", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=SessionSerializer,
            description="Retrieve a session by ID",
            tags=["Sessions"],
        ),
        "put": doc_update(
            request=SessionSerializer,
            response=SessionSerializer,
            description="Update a session by ID",
            tags=["Sessions"],
        ),
        "delete": doc_destroy(description="Delete a session by ID", tags=["Sessions"]),
    }
)
class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            sess = get_object_or_404(Session, pk=pk)
            return Response(SessionSerializer(sess).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching session", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            sess = get_object_or_404(Session, pk=pk)
            ser = SessionSerializer(sess, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            sess = ser.save()
            return Response(SessionSerializer(sess).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating session", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            sess = get_object_or_404(Session, pk=pk)
            sess.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting session", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=SessionFieldSerializer(many=True),
            description="List all session fields",
            tags=["Session Fields"],
        ),
        "post": doc_create(
            request=SessionFieldSerializer,
            response=SessionFieldSerializer,
            description="Create a new session field",
            tags=["Session Fields"],
        ),
    }
)
class SessionFieldList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = SessionField.objects.all()
            return Response(SessionFieldSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching session fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = SessionFieldSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating session field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=SessionFieldSerializer,
            description="Retrieve a session field by ID",
            tags=["Session Fields"],
        ),
        "put": doc_update(
            request=SessionFieldSerializer,
            response=SessionFieldSerializer,
            description="Update a session field by ID",
            tags=["Session Fields"],
        ),
        "delete": doc_destroy(
            description="Delete a session field by ID", tags=["Session Fields"]
        ),
    }
)
class SessionFieldDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(SessionField, pk=pk)
            return Response(SessionFieldSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching session field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(SessionField, pk=pk)
            ser = SessionFieldSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating session field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(SessionField, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting session field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# SessionRegistration CRUD
@document_api_view(
    {
        "get": doc_list(
            response=SessionRegistrationSerializer(many=True),
            parameters=[
                query_param("session", "uuid", False, "Filter by session ID"),
                query_param("guest", "uuid", False, "Filter by guest ID"),
            ],
            description="List all session registrations",
            tags=["Session Registrations"],
        ),
        "post": doc_create(
            request=SessionRegistrationSerializer,
            response=SessionRegistrationSerializer,
            description="Register a guest to a session",
            tags=["Session Registrations"],
        ),
    }
)
class SessionRegistrationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = SessionRegistration.objects.all()
            return Response(SessionRegistrationSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing session registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = SessionRegistrationSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(
                SessionRegistrationSerializer(reg).data, status=status.HTTP_201_CREATED
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating session registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=SessionRegistrationSerializer,
            description="Retrieve a session registration by ID",
            tags=["Session Registrations"],
        ),
        "put": doc_update(
            request=SessionRegistrationSerializer,
            response=SessionRegistrationSerializer,
            description="Update a session registration by ID",
            tags=["Session Registrations"],
        ),
        "delete": doc_destroy(
            description="Delete a session registration by ID",
            tags=["Session Registrations"],
        ),
    }
)
class SessionRegistrationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            reg = get_object_or_404(SessionRegistration, pk=pk)
            return Response(SessionRegistrationSerializer(reg).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching session registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            reg = get_object_or_404(SessionRegistration, pk=pk)
            ser = SessionRegistrationSerializer(reg, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            reg = ser.save()
            return Response(SessionRegistrationSerializer(reg).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating session registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            reg = get_object_or_404(SessionRegistration, pk=pk)
            reg.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting session registration", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=SessionRegistrationSerializer(many=True),
            description="List all registrations for a given session",
            tags=["Session Registrations"],
        )
    }
)
class SessionRegistrationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            regs = SessionRegistration.objects.filter(session_id=pk)
            return Response(SessionRegistrationSerializer(regs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing session registrations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            description="List all session registrations and their guests (with extra_attendees if any)",
            tags=["Session Attendees"],
        )
    }
)
class SessionAllAttendeesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /sessions/{session_pk}/all-attendees/
    Returns a list of all SessionRegistrations (with guest data).
    (If you add extra_attendees to session regs in future, you can expand here.)
    """

    def get(self, request, session_pk):
        try:
            registrations = SessionRegistration.objects.filter(
                session_id=session_pk
            ).select_related("guest")
            results = []
            for reg in registrations:
                guest_data = RestrictedGuestSerializer(reg.guest).data
                results.append(
                    {
                        "session_registration_id": str(reg.id),
                        "guest": guest_data,
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
            description="Get guest for a session registration",
            tags=["Session Registration Attendees"],
        )
    }
)
class SessionRegistrationAttendeesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /session-registrations/{registration_pk}/attendees/
    Returns guest info for this session registration.
    """

    def get(self, request, registration_pk):
        try:
            reg = get_object_or_404(SessionRegistration, pk=registration_pk)
            guest_data = RestrictedGuestSerializer(reg.guest).data
            result = {
                "session_registration_id": str(reg.id),
                "guest": guest_data,
            }
            return Response(result)
        except Exception as e:
            return Response(
                {"detail": "Error fetching attendees", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
