from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError


from Events.models.staff_assignment_models import (
    EventStaffAssignment,
    SessionStaffAssignment,
)
from Events.serializers.staff_assignment_serializers import (
    EventStaffAssignmentSerializer,
    SessionStaffAssignmentSerializer,
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
            response=EventStaffAssignmentSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("user", "uuid", False, "Filter by user ID"),
                query_param("role", "str", False, "Filter by role"),
            ],
            description="List all staff-event assignments",
            tags=["Event Staff Assignments"],
        ),
        "post": doc_create(
            request=EventStaffAssignmentSerializer,
            response=EventStaffAssignmentSerializer,
            description="Assign staff to an event",
            tags=["Event Staff Assignments"],
        ),
    }
)
class EventStaffAssignmentList(APIView):

    def get(self, request):
        try:
            qs = EventStaffAssignment.objects.all()
            return Response(EventStaffAssignmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching assignments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventStaffAssignmentSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            assign = ser.save()
            return Response(
                EventStaffAssignmentSerializer(assign).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventStaffAssignmentSerializer,
            description="Retrieve a staff-event assignment by ID",
            tags=["Event Staff Assignments"],
        ),
        "put": doc_update(
            request=EventStaffAssignmentSerializer,
            response=EventStaffAssignmentSerializer,
            description="Update a staff-event assignment by ID",
            tags=["Event Staff Assignments"],
        ),
        "delete": doc_destroy(
            description="Delete a staff-event assignment by ID",
            tags=["Event Staff Assignments"],
        ),
    }
)
class EventStaffAssignmentDetail(APIView):

    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventStaffAssignment, pk=pk)
            return Response(EventStaffAssignmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventStaffAssignment, pk=pk)
            ser = EventStaffAssignmentSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(EventStaffAssignmentSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventStaffAssignment, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── SessionStaffAssignment ──────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=SessionStaffAssignmentSerializer(many=True),
            parameters=[
                query_param("session", "uuid", False, "Filter by session ID"),
                query_param("user", "uuid", False, "Filter by user ID"),
                query_param("role", "str", False, "Filter by role"),
            ],
            description="List all staff-session assignments",
            tags=["Session Staff Assignments"],
        ),
        "post": doc_create(
            request=SessionStaffAssignmentSerializer,
            response=SessionStaffAssignmentSerializer,
            description="Assign staff to a session",
            tags=["Session Staff Assignments"],
        ),
    }
)
class SessionStaffAssignmentList(APIView):

    def get(self, request):
        try:
            qs = SessionStaffAssignment.objects.all()
            return Response(SessionStaffAssignmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching assignments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = SessionStaffAssignmentSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            assign = ser.save()
            return Response(
                SessionStaffAssignmentSerializer(assign).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=SessionStaffAssignmentSerializer,
            description="Retrieve a staff-session assignment by ID",
            tags=["Session Staff Assignments"],
        ),
        "put": doc_update(
            request=SessionStaffAssignmentSerializer,
            response=SessionStaffAssignmentSerializer,
            description="Update a staff-session assignment by ID",
            tags=["Session Staff Assignments"],
        ),
        "delete": doc_destroy(
            description="Delete a staff-session assignment by ID",
            tags=["Session Staff Assignments"],
        ),
    }
)
class SessionStaffAssignmentDetail(APIView):

    def get(self, request, pk):
        try:
            obj = get_object_or_404(SessionStaffAssignment, pk=pk)
            return Response(SessionStaffAssignmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(SessionStaffAssignment, pk=pk)
            ser = SessionStaffAssignmentSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(SessionStaffAssignmentSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(SessionStaffAssignment, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# View to get all guest data based on event/session/extra_attendee
# endpoint to get all extra attendees on an event registration.
# endpoint to get all events/sessions assigned to a user.
# endpoint to fetch, all sessions for an event, all event/session registrations for an event/session, all accommodations/traveldetails for an event and all accommodations/traveldetails for an event_registration/extra_attendee.
# endpoint to get allowed session/event/guest fields for an event

# endpoint to get guestdata of an event registration(with extra_attendees) and for session registration,session.
