from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from MessageTemplates.models import BroadcastCampaign
from MessageTemplates.serializers import BroadcastCampaignSerializer
from Events.models.whatsapp_message_log import WhatsAppMessageLog
from Events.serializers.whatsapp_message_log_serializer import WhatsAppMessageLogSerializer
from rest_framework.pagination import PageNumberPagination

class BroadcastCampaignViewSet(viewsets.ModelViewSet):
    queryset = BroadcastCampaign.objects.all().order_by("-created_at")
    serializer_class = BroadcastCampaignSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        # Optimization: Annotate stats for list view to avoid N+1 queries
        # Note: This is an approximation if logs grow very large, but good for MVP
        
        # Filters
        sender_id = self.request.query_params.get("sender_phone_number_id")
        if sender_id:
            qs = qs.filter(sender_phone_number_id=sender_id)
            
        return qs

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Add detailed logs (paginated)
        logs_qs = instance.logs.all().order_by("-sent_at")
        
        # Helper to just get stats
        stats = {
            "total": logs_qs.count(),
            "sent": logs_qs.filter(status="sent").count(),
            "delivered": logs_qs.filter(status="delivered").count(),
            "read": logs_qs.filter(status="read").count(),
            "failed": logs_qs.filter(status="failed").count(),
        }
        data["stats"] = stats
        
        # Pagination for logs
        page = self.paginate_queryset(logs_qs)
        if page is not None:
            log_serializer = WhatsAppMessageLogSerializer(page, many=True)
            data["logs"] = self.get_paginated_response(log_serializer.data).data
        else:
            log_serializer = WhatsAppMessageLogSerializer(logs_qs, many=True)
            data["logs"] = log_serializer.data
            
        return Response(data)
