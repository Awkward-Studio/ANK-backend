from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from Events.models.event_registration_model import EventRegistration
from Events.models.conversation_message import ConversationMessage
from Events.serializers.conversation_serializers import ConversationMessageSerializer
from MessageTemplates.services.whatsapp import within_24h_window

class ConversationHistoryView(APIView):
    """
    GET /api/event-registrations/{id}/conversation/
    Returns full chat history for a registration.
    """
    def get(self, request, event_id, registration_id):
        # Verify reg belongs to event
        reg = get_object_or_404(EventRegistration, id=registration_id, event_id=event_id)
        
        messages = ConversationMessage.objects.filter(
            event_registration=reg
        ).order_by('-timestamp')
        
        serializer = ConversationMessageSerializer(messages, many=True)
        return Response(serializer.data)

class ServiceWindowStatusView(APIView):
    """
    GET /api/event-registrations/{id}/service-window/
    Returns status of the 24h service window.
    """
    def get(self, request, event_id, registration_id):
        reg = get_object_or_404(EventRegistration, id=registration_id, event_id=event_id)
        
        in_window = within_24h_window(reg.responded_on)
        remaining_seconds = 0
        
        if in_window and reg.responded_on:
            expiry = reg.responded_on + timedelta(hours=24)
            remaining_seconds = (expiry - timezone.now()).total_seconds()
            
        return Response({
            "in_window": in_window,
            "last_inbound": reg.responded_on,
            "remaining_seconds": max(0, remaining_seconds)
        })
