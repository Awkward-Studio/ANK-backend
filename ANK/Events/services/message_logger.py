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
            updated_count = ConversationMessage.objects.filter(wa_message_id=wa_message_id).update(status=new_status)
            if updated_count == 0:
                logger.warning(f"Attempted to update status for unknown message_id: {wa_message_id}")
            return updated_count > 0
        except Exception as e:
            logger.exception(f"Failed to update status for message {wa_message_id}: {e}")
            return False

    # ─── Send-and-Log Wrappers ─────────────────────────────────────────────
    # These methods SEND the message via WhatsApp AND log it in one call.
    # Use these throughout the codebase for automatic logging.

    @staticmethod
    def send_text(reg: EventRegistration, text: str, message_type: str = 'content') -> str:
        """
        Send a freeform text message AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_freeform_text
        
        phone = getattr(reg.guest, 'phone', None)
        if not phone:
            logger.warning(f"[SEND_TEXT] No phone for reg {reg.id}")
            return ""
        
        try:
            wa_id = send_freeform_text(phone, text)
            MessageLogger.log_outbound(reg, text, wa_id, message_type)
            return wa_id
        except Exception as e:
            logger.exception(f"[SEND_TEXT] Failed for reg {reg.id}: {e}")
            return ""

    @staticmethod
    def send_buttons(reg: EventRegistration, body: str, choices: list, message_type: str = 'content', header: str = None, footer: str = None) -> str:
        """
        Send an interactive button message AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_choice_buttons
        
        phone = getattr(reg.guest, 'phone', None)
        if not phone:
            logger.warning(f"[SEND_BUTTONS] No phone for reg {reg.id}")
            return ""
        
        try:
            wa_id = send_choice_buttons(phone, body, choices, header, footer)
            # Log the body + button titles for context
            button_titles = ", ".join([c.get('title', '') for c in choices])
            content = f"{body}\n[Buttons: {button_titles}]"
            MessageLogger.log_outbound(reg, content, wa_id, message_type)
            return wa_id
        except Exception as e:
            logger.exception(f"[SEND_BUTTONS] Failed for reg {reg.id}: {e}")
            return ""

    @staticmethod
    def send_resume_template(reg: EventRegistration, opener_param: str = None) -> str:
        """
        Send the 'resume conversation' template AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_resume_opener
        
        phone = getattr(reg.guest, 'phone', None)
        if not phone:
            logger.warning(f"[SEND_RESUME] No phone for reg {reg.id}")
            return ""
        
        try:
            wa_id = send_resume_opener(phone, str(reg.id), opener_param)
            MessageLogger.log_outbound(reg, "Resume Conversation Template", wa_id, "template", "resume_conversation")
            return wa_id
        except Exception as e:
            logger.exception(f"[SEND_RESUME] Failed for reg {reg.id}: {e}")
            return ""
