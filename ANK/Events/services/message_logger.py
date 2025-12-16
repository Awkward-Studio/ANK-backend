import logging

from django.utils import timezone
from Events.models.conversation_message import ConversationMessage
from Events.models.event_registration_model import EventRegistration
from Events.models.whatsapp_message_log import WhatsAppMessageLog

logger = logging.getLogger(__name__)


class MessageLogger:
    @staticmethod
    def log_inbound(
        event_registration: EventRegistration,
        content: str,
        message_type: str = "content",
        wa_message_id: str = None,
        media_url: str = None,
        media_type: str = None,
        media_id: str = None,
        metadata: dict = None,
    ):
        """
        Log an inbound message and update the registration's responded_on timestamp.
        """
        try:
            msg = ConversationMessage.objects.create(
                event_registration=event_registration,
                direction="inbound",
                message_type=message_type,
                content=content,
                status="received",
                wa_message_id=wa_message_id,
                media_url=media_url,
                media_type=media_type,
                media_id=media_id,
                metadata=metadata or {},
            )

            # [FIX] Log to WhatsAppMessageLog for unified history view
            if wa_message_id:
                try:
                    phone = getattr(event_registration.guest, "phone", "") or ""
                    # Store only digits
                    guest_wa_id = "".join(c for c in phone if c.isdigit())[-15:]

                    WhatsAppMessageLog.objects.update_or_create(
                        wamid=wa_message_id,
                        defaults={
                            "recipient_id": guest_wa_id,
                            "status": "received",
                            "sent_at": timezone.now(),
                            "event_registration_id": str(event_registration.id),
                            "event_id": str(event_registration.event_id)
                            if event_registration.event_id
                            else None,
                            "template_name": None,
                            "flow_type": "rsvp", # Defaulting to RSVP context for inbound logged here
                            "message_type": message_type,
                            "guest_id": str(event_registration.guest_id)
                            if event_registration.guest_id
                            else None,
                            "guest_name": getattr(
                                event_registration.guest, "name", None
                            ),
                            "direction": "inbound",
                            "body": content,
                            "media_url": media_url,
                            "media_type": media_type,
                            "media_id": media_id,
                        },
                    )
                except Exception as log_err:
                     logger.warning(f"[LOG-INBOUND] Failed to create history log: {log_err}")

            # Update the service window tracker
            event_registration.responded_on = timezone.now()
            event_registration.save(update_fields=["responded_on"])

            return msg
        except Exception as e:
            logger.exception(
                f"Failed to log inbound message for reg {event_registration.id}: {e}"
            )
            return None

    @staticmethod
    def log_outbound(
        event_registration: EventRegistration,
        content: str,
        wa_message_id: str,
        message_type: str = "content",
        template_name: str = None,
        media_url: str = None,
        media_type: str = None,
        media_id: str = None,
        metadata: dict = None,
    ):
        """
        Log an outbound message to ConversationMessage and WhatsAppMessageLog for delivery tracking.
        """
        try:
            msg = ConversationMessage.objects.create(
                event_registration=event_registration,
                direction="outbound",
                message_type=message_type,
                content=content,
                status="sent",
                wa_message_id=wa_message_id,
                template_name=template_name,
                media_url=media_url,
                media_type=media_type,
                media_id=media_id,
                metadata=metadata or {},
            )

            # Also create WhatsAppMessageLog for delivery status tracking
            if wa_message_id:
                try:
                    # Get phone digits for recipient_id
                    phone = getattr(event_registration.guest, "phone", "") or ""
                    recipient_id = "".join(c for c in phone if c.isdigit())[-15:]

                    # Map conversation message_type to WhatsAppMessageLog message_type
                    log_message_type = message_type
                    if message_type == "content":
                        log_message_type = "custom"
                    elif message_type not in (
                        "rsvp",
                        "custom",
                        "travel",
                        "template",
                        "bulk",
                    ):
                        log_message_type = "custom"

                    WhatsAppMessageLog.objects.update_or_create(
                        wamid=wa_message_id,
                        defaults={
                            "recipient_id": recipient_id,
                            "status": "sent",
                            "sent_at": timezone.now(),
                            "message_type": log_message_type,
                            "template_name": template_name,
                            "event_registration_id": str(event_registration.id),
                            "event_id": str(event_registration.event_id)
                            if event_registration.event_id
                            else None,
                            "guest_id": str(event_registration.guest_id)
                            if event_registration.guest_id
                            else None,
                            "guest_name": getattr(
                                event_registration.guest, "name", None
                            ),
                            "direction": "outbound",
                            "body": content,
                            "media_url": media_url,
                            "media_type": media_type,
                            "media_id": media_id,
                        },
                    )
                    logger.info(
                        f"[MESSAGE-LOG] Created delivery tracking for wamid={wa_message_id[:30]}..."
                    )
                except Exception as log_err:
                    # Non-fatal - don't fail if WhatsAppMessageLog creation fails
                    logger.warning(
                        f"[MESSAGE-LOG] Failed to create delivery tracking: {log_err}"
                    )

            return msg
        except Exception as e:
            logger.exception(
                f"Failed to log outbound message for reg {event_registration.id}: {e}"
            )
            return None

    @staticmethod
    def update_status(wa_message_id: str, new_status: str):
        """
        Update the status of a message based on WhatsApp callback.
        Updates both ConversationMessage and WhatsAppMessageLog.
        """
        try:
            # Update ConversationMessage
            updated_count = ConversationMessage.objects.filter(
                wa_message_id=wa_message_id
            ).update(status=new_status)
            if updated_count == 0:
                logger.warning(
                    f"Attempted to update status for unknown message_id: {wa_message_id}"
                )

            # Also update WhatsAppMessageLog for delivery tracking
            try:
                msg_log = WhatsAppMessageLog.objects.filter(wamid=wa_message_id).first()
                if msg_log:
                    # Only upgrade status, never downgrade (except for failed)
                    status_order = {"sent": 1, "delivered": 2, "read": 3, "failed": 0}
                    current_order = status_order.get(msg_log.status, 0)
                    new_order = status_order.get(new_status, 0)

                    if new_order > current_order or new_status == "failed":
                        msg_log.status = new_status
                        if new_status == "delivered":
                            msg_log.delivered_at = timezone.now()
                        elif new_status == "read":
                            msg_log.read_at = timezone.now()
                        elif new_status == "failed":
                            msg_log.failed_at = timezone.now()
                        msg_log.save()
                        logger.info(
                            f"[MESSAGE-LOG] Updated status for wamid={wa_message_id[:30]}... to {new_status}"
                        )
            except Exception as log_err:
                logger.warning(
                    f"[MESSAGE-LOG] Failed to update WhatsAppMessageLog status: {log_err}"
                )

            return updated_count > 0
        except Exception as e:
            logger.exception(
                f"Failed to update status for message {wa_message_id}: {e}"
            )
            return False

    # ─── Send-and-Log Wrappers ─────────────────────────────────────────────
    # These methods SEND the message via WhatsApp AND log it in one call.
    # Use these throughout the codebase for automatic logging.

    @staticmethod
    def send_text(
        reg: EventRegistration, text: str, message_type: str = "content"
    ) -> str:
        """
        Send a freeform text message AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_freeform_text

        phone = getattr(reg.guest, "phone", None)
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
    def send_buttons(
        reg: EventRegistration,
        body: str,
        choices: list,
        message_type: str = "content",
        header: str = None,
        footer: str = None,
    ) -> str:
        """
        Send an interactive button message AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_choice_buttons

        phone = getattr(reg.guest, "phone", None)
        if not phone:
            logger.warning(f"[SEND_BUTTONS] No phone for reg {reg.id}")
            return ""

        try:
            wa_id = send_choice_buttons(phone, body, choices, header, footer)
            # Log the body + button titles for context
            button_titles = ", ".join([c.get("title", "") for c in choices])
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

        phone = getattr(reg.guest, "phone", None)
        if not phone:
            logger.warning(f"[SEND_RESUME] No phone for reg {reg.id}")
            return ""

        try:
            wa_id = send_resume_opener(phone, str(reg.id), opener_param)
            MessageLogger.log_outbound(
                reg,
                "Resume Conversation Template",
                wa_id,
                "template",
                "resume_conversation",
            )
            return wa_id
        except Exception as e:
            logger.exception(f"[SEND_RESUME] Failed for reg {reg.id}: {e}")
            return ""

    @staticmethod
    def send_media_message(
        reg: EventRegistration,
        media_type: str,
        media_url: str,
        caption: str = None,
        message_type: str = "content",
    ) -> str:
        """
        Send a media message AND log it.
        Returns the WhatsApp message ID.
        """
        from MessageTemplates.services.whatsapp import send_media

        phone = getattr(reg.guest, "phone", None)
        if not phone:
            logger.warning(f"[SEND_MEDIA] No phone for reg {reg.id}")
            return ""

        try:
            wa_id = send_media(phone, media_type, media_url, caption)
            MessageLogger.log_outbound(
                reg,
                content=caption,  # Log caption as the main text content
                wa_message_id=wa_id,
                message_type=message_type,
                media_url=media_url,
                media_type=media_type,
            )
            return wa_id
        except Exception as e:
            logger.exception(f"[SEND_MEDIA] Failed for reg {reg.id}: {e}")
            return ""
