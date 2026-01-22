from rest_framework import serializers
import MessageTemplates.models
from MessageTemplates.models import (
    MessageTemplate,
    MessageTemplateVariable,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
)

from django.core.exceptions import ValidationError
from django.db import transaction


class MessageTemplateVariableSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MessageTemplateVariable
        fields = [
            "id",
            "template",
            "variable_name",
            "variable_value",
            "variable_description",
            "variable_position",
        ]


class MessageTemplateSerializer(serializers.ModelSerializer):
    """
    Read serializer — includes nested variables.
    """

    variables = MessageTemplateVariableSerializer(
        many=True, read_only=True, required=False
    )
    eventId = serializers.UUIDField(source="event_id", allow_null=True, required=False)

    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "eventId",
            "name",
            "message",
            "desc",
            "is_rsvp_message",
            "media_type",
            "media_url",
            "media_id",
            "variables",
            "created_at",
            "updated_at",
        ]


class MessageTemplateWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer — accepts optional nested 'variables' to create/replace.
    On update, if 'variables' is provided, the set is replaced atomically by upsert.
    """

    variables = MessageTemplateVariableSerializer(many=True, required=False)
    eventId = serializers.UUIDField(source="event_id", allow_null=True, required=False)

    class Meta:
        model = MessageTemplate
        fields = [
            "eventId",
            "name",
            "message",
            "desc",
            "is_rsvp_message",
            "media_type",
            "media_url",
            "media_id",
            "variables",
        ]

    @staticmethod
    def true_upsert_template_variables(
        template: MessageTemplate,
        variables: list[dict],
        delete_missing: bool = True,
    ) -> None:
        """
        Upsert by variable_name:
        • update existing (match on template+variable_name)
        • create missing
        • optionally delete ones not present in payload
        """
        existing = {v.variable_name: v for v in template.variables.all()}
        seen = set()
        to_create, to_update = [], []

        for v in variables:
            name = (v.get("variable_name") or "").strip()
            if not name:
                raise ValidationError(
                    {"variables": [{"variable_name": ["This field is required."]}]}
                )
            seen.add(name)

            if name in existing:
                obj = existing[name]
                obj.variable_value = v.get("variable_value", obj.variable_value or "")
                obj.variable_description = v.get(
                    "variable_description", obj.variable_description or ""
                )
                obj.variable_position = v.get(
                    "variable_position", obj.variable_position or 0
                )
                to_update.append(obj)
            else:
                to_create.append(
                    MessageTemplateVariable(
                        template=template,
                        variable_name=name,
                        variable_value=v.get("variable_value", ""),
                        variable_description=v.get("variable_description", ""),
                        variable_position=v.get("variable_position", 0),
                    )
                )

        if delete_missing:
            missing = set(existing.keys()) - seen
            if missing:
                template.variables.filter(variable_name__in=list(missing)).delete()

        if to_create:
            MessageTemplateVariable.objects.bulk_create(to_create)
        if to_update:
            MessageTemplateVariable.objects.bulk_update(
                to_update,
                fields=["variable_value", "variable_description", "variable_position"],
            )

    def _upsert_variables(self, template, variables, replace=False):
        if replace:
            template.variables.all().delete()
        bulk = []
        for v in variables:
            bulk.append(
                MessageTemplateVariable(
                    template=template,
                    variable_name=v.get("variable_name"),
                    variable_value=v.get("variable_value", ""),
                    variable_description=v.get("variable_description", ""),
                    variable_position=v.get("variable_position", 0),
                )
            )
        if bulk:
            MessageTemplateVariable.objects.bulk_create(bulk)

    def create(self, validated_data):
        vars_data = validated_data.pop("variables", [])
        template = MessageTemplate.objects.create(**validated_data)
        self._upsert_variables(template, vars_data, replace=True)
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        vars_data = validated_data.pop("variables", None)
        delete_missing = self.context.get("delete_missing", True)

        # update base fields
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        # upsert variables only if provided
        if vars_data is not None:
            vser = MessageTemplateVariableSerializer(data=vars_data, many=True)
            vser.is_valid(raise_exception=True)
            # vser.validated_data contains dicts with variable_* fields
            MessageTemplateWriteSerializer.true_upsert_template_variables(
                instance, vser.validated_data, delete_missing
            )

        return instance


class WhatsAppBusinessAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for WhatsApp Business Account.
    Never expose the encrypted token.
    """

    class Meta:
        model = WhatsAppBusinessAccount
        fields = [
            "id",
            "waba_id",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class WhatsAppPhoneNumberSerializer(serializers.ModelSerializer):
    """
    Read serializer for WhatsApp Phone Number.
    Never expose encrypted tokens or full WABA details.
    """

    class Meta:
        model = WhatsAppPhoneNumber
        fields = [
            "id",
            "phone_number_id",
            "asset_id",
            "waba_id",
            "display_phone_number",
            "verified_name",
            "quality_rating",
            "messaging_limit_tier",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
            "last_used_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_used_at"]


class WhatsAppPhoneNumberWriteSerializer(serializers.Serializer):
    """
    Write serializer for storing/updating WhatsApp phone numbers.
    Accepts access_token for storage but never returns it.
    Token storage is OPTIONAL - phone number will be saved even if encryption fails.
    """

    phone_number_id = serializers.CharField(
        max_length=100, required=True, help_text="Phone Number ID from Meta"
    )
    asset_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    waba_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default="",
        help_text="WABA ID (optional, may not be available from embedded signup)"
    )
    access_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default="",
        help_text="Access token (optional, will be encrypted if WHATSAPP_ENCRYPTION_KEY is set)",
    )
    display_phone_number = serializers.CharField(
        max_length=20, required=True, help_text="Display format like +919876543210"
    )
    verified_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    quality_rating = serializers.ChoiceField(
        choices=["GREEN", "YELLOW", "RED", "UNKNOWN"],
        default="UNKNOWN",
        required=False,
    )
    messaging_limit_tier = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    is_default = serializers.BooleanField(default=False, required=False)

    def create(self, validated_data):
        """
        Create or update WhatsAppBusinessAccount and WhatsAppPhoneNumber.
        Token storage is optional - will log warning if encryption fails but still save the phone number.
        """
        import logging
        from django.conf import settings
        logger = logging.getLogger(__name__)
        
        access_token = validated_data.pop("access_token", "")
        waba_id = validated_data.get("waba_id", "") or validated_data.get("asset_id", "")
        phone_number_id = validated_data.get("phone_number_id")
        
        # Use asset_id as waba_id fallback if waba_id is empty
        if not waba_id:
            waba_id = phone_number_id  # Last resort fallback

        # Get or create WABA
        waba, created = WhatsAppBusinessAccount.objects.get_or_create(
            waba_id=waba_id,
            defaults={
                "name": validated_data.get("verified_name", f"WABA {waba_id}"),
                "is_active": True,
            },
        )

        # Store token at WABA level (OPTIONAL - don't fail if encryption key is missing)
        token_stored = False
        if access_token:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if encryption_key:
                try:
                    waba.set_token(access_token)
                    waba.save()
                    token_stored = True
                    logger.info(f"[STORE_PHONE] Successfully encrypted and stored token for WABA {waba_id}")
                except Exception as e:
                    logger.warning(f"[STORE_PHONE] Failed to encrypt token for WABA {waba_id}: {e}")
            else:
                logger.warning(
                    f"[STORE_PHONE] WHATSAPP_ENCRYPTION_KEY not set - skipping token storage for WABA {waba_id}. "
                    "Phone number will be saved without token. Set the encryption key to enable token storage."
                )
        else:
            logger.info(f"[STORE_PHONE] No access_token provided for WABA {waba_id}")

        # Create or update phone number (this always succeeds regardless of token storage)
        phone, created = WhatsAppPhoneNumber.objects.update_or_create(
            phone_number_id=phone_number_id,
            defaults={
                "business_account": waba,
                "asset_id": validated_data.get("asset_id", ""),
                "waba_id": waba_id,
                "display_phone_number": validated_data.get("display_phone_number"),
                "verified_name": validated_data.get("verified_name", ""),
                "quality_rating": validated_data.get("quality_rating", "UNKNOWN"),
                "messaging_limit_tier": validated_data.get("messaging_limit_tier", ""),
                "is_active": True,
                "is_default": validated_data.get("is_default", False),
            },
        )
        
        logger.info(
            f"[STORE_PHONE] Phone number {'created' if created else 'updated'}: {phone_number_id}, "
            f"token_stored={token_stored}"
        )

        return phone


class BroadcastCampaignSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = MessageTemplates.models.BroadcastCampaign
        fields = [
            "id",
            "name",
            "template_name",
            "sender_phone_number_id",
            "total_recipients",
            "status",
            "created_at",
            "metadata",
            "stats",
        ]
        read_only_fields = ["id", "created_at", "stats"]

    def get_stats(self, obj):
        # Perform aggregation if this is a detail view or if needed
        # For list views, we might want to prefetch or annotate, 
        # but for now, let's just do a simple aggregation.
        # This might be costly for large lists, so viewset should invoke annotations.
        
        # If the object has 'annotated_stats', use it (optimization for list view)
        if hasattr(obj, 'annotated_stats'):
            return obj.annotated_stats

        # Fallback to query
        logs = obj.logs.all()
        total = logs.count()
        delivered = logs.filter(status='delivered').count()
        read = logs.filter(status='read').count()
        failed = logs.filter(status='failed').count()
        sent = logs.filter(status='sent').count()
        
        return {
            "sent": sent,
            "delivered": delivered,
            "read": read,
            "failed": failed,
            "total": total
        }
