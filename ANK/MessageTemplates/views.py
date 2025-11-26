from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from Events.models.event_model import Event
from MessageTemplates.models import MessageTemplate, MessageTemplateVariable
from MessageTemplates.serializers import (
    MessageTemplateSerializer,
    MessageTemplateWriteSerializer,
    MessageTemplateVariableSerializer,
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


# ───────────────────────── MessageTemplate: List/Create ─────────────────────────
@document_api_view(
    {
        "get": doc_list(
            response=MessageTemplateSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event UUID"),
                query_param("name", "str", False, "Filter by name (icontains)"),
                query_param("is_rsvp_message", "bool", False, "Filter RSVP templates"),
            ],
            description="List message templates (optionally filter by event/name/is_rsvp_message).",
            tags=["Message Templates"],
        ),
        "post": doc_create(
            request=MessageTemplateWriteSerializer,
            response=MessageTemplateSerializer,
            description="Create a message template (optionally with nested variables).",
            tags=["Message Templates"],
        ),
    }
)
class MessageTemplateList(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            qs = MessageTemplate.objects.all().prefetch_related("variables")
            event = request.GET.get("event")
            name = request.GET.get("name")
            is_rsvp = request.GET.get("is_rsvp_message")

            if event:
                qs = qs.filter(event__id=event)
            if name:
                qs = qs.filter(name__icontains=name)
            if is_rsvp is not None:
                is_rsvp_bool = str(is_rsvp).lower() in ("1", "true", "yes", "on")
                qs = qs.filter(is_rsvp_message=is_rsvp_bool)

            return Response(MessageTemplateSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching message templates", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = MessageTemplateWriteSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(
                MessageTemplateSerializer(obj).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating message template", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ───────────────────────── MessageTemplate: Detail/Update/Delete ─────────────────
@document_api_view(
    {
        "get": doc_retrieve(
            response=MessageTemplateSerializer,
            description="Retrieve a message template by ID (with variables).",
            tags=["Message Templates"],
        ),
        "put": doc_update(
            request=MessageTemplateWriteSerializer,
            response=MessageTemplateSerializer,
            description="Update a message template by ID (replace nested variables if provided).",
            tags=["Message Templates"],
        ),
        "delete": doc_destroy(
            description="Delete a message template by ID.",
            tags=["Message Templates"],
        ),
    }
)
class MessageTemplateDetail(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        try:
            obj = get_object_or_404(
                MessageTemplate.objects.prefetch_related("variables"), pk=pk
            )
            return Response(MessageTemplateSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching message template", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(MessageTemplate, pk=pk)
            ser = MessageTemplateWriteSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(MessageTemplateSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating message template", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(MessageTemplate, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting message template", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ───────────────────────── Variables: List/Create ─────────────────────────
@document_api_view(
    {
        "get": doc_list(
            response=MessageTemplateVariableSerializer(many=True),
            parameters=[
                query_param("template", "uuid", False, "Filter by template UUID"),
                query_param(
                    "name", "str", False, "Filter by variable name (icontains)"
                ),
            ],
            description="List message template variables (filterable).",
            tags=["Message Template Variables"],
        ),
        "post": doc_create(
            request=MessageTemplateVariableSerializer,
            response=MessageTemplateVariableSerializer,
            description="Create a message template variable.",
            tags=["Message Template Variables"],
        ),
    }
)
class MessageTemplateVariableList(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            qs = MessageTemplateVariable.objects.all()
            template = request.GET.get("template")
            name = request.GET.get("name")

            if template:
                qs = qs.filter(template__id=template)
            if name:
                qs = qs.filter(variable_name__icontains=name)

            return Response(MessageTemplateVariableSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching template variables", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = MessageTemplateVariableSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(
                MessageTemplateVariableSerializer(obj).data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating template variable", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ───────────────────────── Variables: Detail/Update/Delete ─────────────────
@document_api_view(
    {
        "get": doc_retrieve(
            response=MessageTemplateVariableSerializer,
            description="Retrieve a message template variable by ID.",
            tags=["Message Template Variables"],
        ),
        "put": doc_update(
            request=MessageTemplateVariableSerializer,
            response=MessageTemplateVariableSerializer,
            description="Update a message template variable by ID.",
            tags=["Message Template Variables"],
        ),
        "delete": doc_destroy(
            description="Delete a message template variable by ID.",
            tags=["Message Template Variables"],
        ),
    }
)
class MessageTemplateVariableDetail(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        try:
            obj = get_object_or_404(MessageTemplateVariable, pk=pk)
            return Response(MessageTemplateVariableSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching template variable", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(MessageTemplateVariable, pk=pk)
            ser = MessageTemplateVariableSerializer(
                obj, data=request.data, partial=True
            )
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            return Response(MessageTemplateVariableSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating template variable", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(MessageTemplateVariable, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting template variable", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=MessageTemplateSerializer(many=True),
            description="List message templates for a given event (by event_pk).",
            tags=["Message Templates"],
        )
    }
)
class EventMessageTemplatesAPIView(APIView):
    permission_classes = [IsAuthenticated]
    """
    GET /events/<uuid:event_pk>/message-templates/
    """

    def get(self, request, event_pk):
        try:
            event = get_object_or_404(Event, pk=event_pk)
            qs = (
                MessageTemplate.objects.filter(event=event)
                .select_related("event")
                .prefetch_related("variables")
            )
            return Response(MessageTemplateSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching templates for event", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
