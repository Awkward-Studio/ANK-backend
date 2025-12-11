from rest_framework import serializers
from Events.models.conversation_message import ConversationMessage

class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = [
            'id',
            'direction',
            'message_type',
            'content',
            'timestamp',
            'status',
            'wa_message_id',
            'template_name',
            'metadata'
        ]
        read_only_fields = fields
