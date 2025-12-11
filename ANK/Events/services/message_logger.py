import logging
from django.utils import timezone
from Events.models.conversation_message import ConversationMessage
from Events.models.event_registration_model import EventRegistration

logger = logging.getLogger(__name__)

class MessageLogger:
    @staticmethod
    def log_inbound(event_registration: EventRegistration, content: str, message_type: str = 'content', wa_message_id: str = None, metadata: dict = None):
        """
        Log an inbound message and update the registration's responded_on timestamp.
        """
        try:
            msg = ConversationMessage.objects.create(
                event_registration=event_registration,
                direction='inbound',
                message_type=message_type,
                content=content,
                status='received',
                wa_message_id=wa_message_id,
                metadata=metadata or {}
            )
            
            # Update the service window tracker
            event_registration.responded_on = timezone.now()
            event_registration.save(update_fields=['responded_on'])
            
            return msg
        except Exception as e:
            logger.exception(f"Failed to log inbound message for reg {event_registration.id}: {e}")
            return None

    @staticmethod
    def log_outbound(event_registration: EventRegistration, content: str, wa_message_id: str, message_type: str = 'content', template_name: str = None, metadata: dict = None):
        """
        Log an outbound message.
        """
        try:
            msg = ConversationMessage.objects.create(
                event_registration=event_registration,
                direction='outbound',
                message_type=message_type,
                content=content,
                status='sent',
                wa_message_id=wa_message_id,
                template_name=template_name,
                metadata=metadata or {}
            )
            return msg
        except Exception as e:
            logger.exception(f"Failed to log outbound message for reg {event_registration.id}: {e}")
            return None

    @staticmethod
    def update_status(wa_message_id: str, new_status: str):
        """
        Update the status of a message based on WhatsApp callback.
        """
        try:
            # Map WhatsApp statuses to our statuses if needed
            # sent, delivered, read, failed are standard in both
            
            updated_count = ConversationMessage.objects.filter(wa_message_id=wa_message_id).update(status=new_status)
            if updated_count == 0:
                logger.warning(f"Attempted to update status for unknown message_id: {wa_message_id}")
            return updated_count > 0
        except Exception as e:
            logger.exception(f"Failed to update status for message {wa_message_id}: {e}")
            return False
