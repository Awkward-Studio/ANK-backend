from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from Events.models.event_model import Event
from MessageTemplates.models import MessageTemplate, MessageTemplateVariable, FlowBlueprint, FlowSession
from MessageTemplates.serializers import (
    MessageTemplateSerializer,
    MessageTemplateWriteSerializer,
    MessageTemplateVariableSerializer,
    FlowBlueprintSerializer,
    FlowSessionSerializer,
)
from MessageTemplates.services.flow_runner import FlowRunner

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


class FlowBlueprintViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FlowBlueprint.objects.all()
    serializer_class = FlowBlueprintSerializer

    def _start_or_reset_session(self, blueprint, registration, sender_id=None, campaign_id=None):
        session, created = FlowSession.objects.get_or_create(
            registration=registration,
            flow=blueprint,
            defaults={"status": "RUNNING"},
        )

        # [FIX] Always reset session to RUNNING and clear old state when manually triggered
        session.status = "RUNNING"
        session.current_node_id = None
        session.context_data = {}
        session.history = []
        session.error_details = None
        session.save(
            update_fields=[
                "status",
                "current_node_id",
                "context_data",
                "history",
                "error_details",
                "last_interaction",
            ]
        )

        runner = FlowRunner(session, sender_phone_number_id=sender_id, campaign_id=campaign_id)
        runner.start()
        return session

    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        try:
            blueprint = self.get_object()
        except:
            return Response({"ok": False, "detail": f"Flow blueprint with ID {pk} not found on this server."}, status=status.HTTP_404_NOT_FOUND)
            
        reg_id = request.data.get("registration_id")
        sender_id = request.data.get("sender_phone_number_id")
        campaign_id = request.data.get("campaign_id")
        
        if not reg_id:
            return Response({"ok": False, "detail": "registration_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not blueprint.is_active:
            return Response({"ok": False, "detail": "Flow blueprint is inactive"}, status=status.HTTP_400_BAD_REQUEST)
            
        from Events.models.event_registration_model import EventRegistration
        try:
            registration = EventRegistration.objects.get(pk=reg_id)
        except EventRegistration.DoesNotExist:
            return Response({"ok": False, "detail": f"Registration with ID {reg_id} not found on this server."}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            session = self._start_or_reset_session(blueprint, registration, sender_id=sender_id, campaign_id=campaign_id)
        except Exception as e:
            return Response({"ok": False, "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            "ok": True,
            "status": "Flow started", 
            "session_id": session.id,
            "session_status": session.status
        })

    @action(detail=True, methods=['post'])
    def start_batch(self, request, pk=None):
        blueprint = self.get_object()
        registration_ids = request.data.get("registration_ids") or []
        sender_id = request.data.get("sender_phone_number_id")
        campaign_id = request.data.get("campaign_id")

        if not isinstance(registration_ids, list) or not registration_ids:
            return Response(
                {"ok": False, "detail": "registration_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not blueprint.is_active:
            return Response({"ok": False, "detail": "Flow blueprint is inactive"}, status=status.HTTP_400_BAD_REQUEST)

        from Events.models.event_registration_model import EventRegistration

        registrations = EventRegistration.objects.filter(pk__in=registration_ids).select_related("guest", "event")
        registration_map = {str(reg.id): reg for reg in registrations}

        results = []
        for reg_id in registration_ids:
            registration = registration_map.get(str(reg_id))
            if not registration:
                results.append({
                    "registration_id": str(reg_id),
                    "ok": False,
                    "detail": "registration not found",
                })
                continue

            try:
                session = self._start_or_reset_session(blueprint, registration, sender_id=sender_id, campaign_id=campaign_id)
                results.append({
                    "registration_id": str(registration.id),
                    "ok": True,
                    "session_id": str(session.id),
                    "session_status": session.status,
                })
            except Exception as exc:
                results.append({
                    "registration_id": str(registration.id),
                    "ok": False,
                    "detail": str(exc),
                })

        success_count = sum(1 for item in results if item.get("ok"))
        return Response({
            "ok": success_count > 0,
            "status": "Batch flow started",
            "results": results,
            "success_count": success_count,
            "failure_count": len(results) - success_count,
        })


class FlowSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FlowSession.objects.all()
    serializer_class = FlowSessionSerializer

    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        session = self.get_object()
        sender_id = request.data.get("sender_phone_number_id")
        if not session.flow.is_active:
            return Response({"ok": False, "detail": "Flow blueprint is inactive"}, status=status.HTTP_400_BAD_REQUEST)
        # Match blueprint start_flow: always reset so FlowRunner.start() runs (it no-ops unless status is RUNNING).
        session.status = "RUNNING"
        session.current_node_id = None
        session.context_data = {}
        session.history = []
        session.error_details = None
        session.save(
            update_fields=[
                "status",
                "current_node_id",
                "context_data",
                "history",
                "error_details",
                "last_interaction",
            ]
        )
        runner = FlowRunner(session, sender_phone_number_id=sender_id)
        try:
            runner.start()
        except Exception as e:
            return Response({"ok": False, "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "ok": True,
                "status": "Flow started",
                "session_status": session.status,
                "session_id": session.id,
            }
        )
