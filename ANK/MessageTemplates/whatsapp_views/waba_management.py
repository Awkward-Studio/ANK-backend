import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
import os

from MessageTemplates.models import WhatsAppBusinessAccount
from MessageTemplates.serializers import WhatsAppBusinessAccountSerializer

logger = logging.getLogger(__name__)
WEBHOOK_SECRET = os.getenv("DJANGO_RSVP_SECRET", "")

class WABAListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            return Response({"error": "Unauthorized"}, status=403)
            
        qs = WhatsAppBusinessAccount.objects.all()
        ser = WhatsAppBusinessAccountSerializer(qs, many=True)
        return Response(ser.data)

    def post(self, request):
        token = request.headers.get("X-Webhook-Token", "")
        if not WEBHOOK_SECRET or token != WEBHOOK_SECRET:
            return Response({"error": "Unauthorized"}, status=403)
            
        waba_id = request.data.get("waba_id")
        name = request.data.get("name")
        access_token = request.data.get("access_token")
        
        if not all([waba_id, name, access_token]):
            return Response({"error": "Missing required fields"}, status=400)
            
        waba, created = WhatsAppBusinessAccount.objects.update_or_create(
            waba_id=waba_id,
            defaults={
                "name": name,
                "is_active": True
            }
        )
        waba.set_token(access_token)
        waba.save()
        
        ser = WhatsAppBusinessAccountSerializer(waba)
        return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
