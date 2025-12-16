from rest_framework import serializers

from Events.models.whatsapp_message_log import WhatsAppMessageLog


class WhatsAppMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessageLog
        fields = [
            "id",
            "wamid",
            "recipient_id",
            "status",
            "direction",
            "message_type",
            "template_name",
            "body",
            "media_url",
            "media_type",
            "media_id",
            "sent_at",
            "delivered_at",
            "read_at",
            "failed_at",
            "error_code",
            "error_message",
            "guest_name",
            "event_id",
            "event_registration_id",
            "guest_id",
        ]
