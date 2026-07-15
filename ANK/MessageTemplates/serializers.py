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


def _normalize_display_phone_number(value: str) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())


def _fetch_meta_phone_numbers(waba_id: str, access_token: str) -> list[dict]:
    import requests

    response = requests.get(
        f"https://graph.facebook.com/v20.0/{waba_id}/phone_numbers",
        params={
            "access_token": access_token,
            "fields": (
                "id,display_phone_number,verified_name,quality_rating,"
                "messaging_limit_tier,code_verification_status,name_status,"
                "new_name_status,account_mode,platform_type,is_official_business_account"
            ),
            "limit": 100,
        },
        timeout=10,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        error = payload.get("error") or {}
        message = error.get("message") or response.text[:300]
        raise serializers.ValidationError({"waba_id": f"Meta could not verify this WABA: {message}"})

    return payload.get("data") or []


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
            "normalized_display_phone_number",
            "verified_name",
            "quality_rating",
            "messaging_limit_tier",
            "is_active",
            "is_default",
            "meta_status",
            "meta_status_reason",
            "meta_last_checked_at",
            "meta_access_state",
            "meta_seen_in_waba",
            "meta_last_attempt_at",
            "meta_last_success_at",
            "meta_fetch_error_code",
            "meta_fetch_error_message",
            "meta_details_snapshot",
            "code_verification_status",
            "name_status",
            "new_name_status",
            "account_mode",
            "platform_type",
            "is_official_business_account",
            "is_usable",
            "usability_reason",
            "created_at",
            "updated_at",
            "last_used_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "last_used_at",
            "normalized_display_phone_number",
            "meta_status",
            "meta_status_reason",
            "meta_last_checked_at",
            "meta_access_state",
            "meta_seen_in_waba",
            "meta_last_attempt_at",
            "meta_last_success_at",
            "meta_fetch_error_code",
            "meta_fetch_error_message",
            "meta_details_snapshot",
            "code_verification_status",
            "name_status",
            "new_name_status",
            "account_mode",
            "platform_type",
            "is_official_business_account",
            "is_usable",
            "usability_reason",
        ]


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
        display_phone_number = validated_data.get("display_phone_number", "")
        
        # Use asset_id as waba_id fallback if waba_id is empty
        if not waba_id:
            waba_id = phone_number_id  # Last resort fallback

        normalized_display = _normalize_display_phone_number(display_phone_number)

        def _existing_duplicate(normalized_number: str):
            if not normalized_number:
                return None
            queryset = WhatsAppPhoneNumber.objects.exclude(phone_number_id=phone_number_id)
            return (
                queryset.filter(normalized_display_phone_number=normalized_number).first()
                or next(
                    (
                        existing
                        for existing in queryset
                        if _normalize_display_phone_number(existing.display_phone_number) == normalized_number
                    ),
                    None,
                )
            )

        existing_duplicate = _existing_duplicate(normalized_display)
        if existing_duplicate:
            raise serializers.ValidationError(
                {
                    "display_phone_number": (
                        "This WhatsApp number is already registered in ANK "
                        f"under WABA {existing_duplicate.waba_id}. Delete the existing record before "
                        "onboarding the same number again."
                    )
                }
            )

        existing_waba = WhatsAppBusinessAccount.objects.filter(waba_id=waba_id).first()
        verification_token = access_token or (existing_waba.get_token() if existing_waba else "")
        if not verification_token:
            raise serializers.ValidationError(
                {"access_token": "An account token is required to verify this WABA with Meta before saving."}
            )

        meta_numbers = _fetch_meta_phone_numbers(waba_id, verification_token)
        meta_by_id = {str(item.get("id")): item for item in meta_numbers if item.get("id")}
        meta_phone = meta_by_id.get(str(phone_number_id))
        if not meta_phone:
            raise serializers.ValidationError(
                {
                    "phone_number_id": (
                        "Meta verification failed: this phone number does not appear "
                        "under the submitted WABA for the supplied token."
                    )
                }
            )

        meta_display_phone_number = meta_phone.get("display_phone_number") or display_phone_number
        normalized_meta_display = _normalize_display_phone_number(meta_display_phone_number)
        existing_duplicate = _existing_duplicate(normalized_meta_display)
        if existing_duplicate:
            raise serializers.ValidationError(
                {
                    "display_phone_number": (
                        "Meta returned a WhatsApp number already registered in ANK "
                        f"under WABA {existing_duplicate.waba_id}. Delete the existing record before "
                        "onboarding the same number again."
                    )
                }
            )

        platform_type = str(meta_phone.get("platform_type") or "").upper()
        if not platform_type:
            raise serializers.ValidationError(
                {
                    "platform_type": (
                        "Meta did not return platform_type for this number. ANK cannot confirm "
                        "that it is a Cloud API sender."
                    )
                }
            )
        if platform_type != "CLOUD_API":
            raise serializers.ValidationError(
                {
                    "platform_type": (
                        f"Meta reports this number as {platform_type}, not CLOUD_API. "
                        "ANK cannot use it as a Cloud API sender."
                    )
                }
            )

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
                "display_phone_number": meta_display_phone_number,
                "normalized_display_phone_number": normalized_meta_display,
                "verified_name": meta_phone.get("verified_name") or validated_data.get("verified_name", ""),
                "quality_rating": meta_phone.get("quality_rating") or validated_data.get("quality_rating", "UNKNOWN"),
                "messaging_limit_tier": meta_phone.get("messaging_limit_tier") or validated_data.get("messaging_limit_tier", ""),
                "code_verification_status": meta_phone.get("code_verification_status") or "",
                "name_status": meta_phone.get("name_status") or "",
                "new_name_status": meta_phone.get("new_name_status") or "",
                "account_mode": meta_phone.get("account_mode") or "",
                "platform_type": meta_phone.get("platform_type") or "",
                "is_official_business_account": meta_phone.get("is_official_business_account"),
                "meta_seen_in_waba": True,
                "meta_access_state": "reachable",
                "meta_details_snapshot": meta_phone,
                "is_active": True,
                "is_default": validated_data.get("is_default", False),
                "meta_status": "active",
                "meta_status_reason": "",
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


class FlowBlueprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplates.models.FlowBlueprint
        fields = [
            "id",
            "name",
            "trigger_keyword",
            "graph_json",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_trigger_keyword(self, value):
        if value:
            return value.strip() or None
        return value


class FlowSessionSerializer(serializers.ModelSerializer):
    flow_name = serializers.CharField(source="flow.name", read_only=True)
    registration_details = serializers.SerializerMethodField()

    class Meta:
        model = MessageTemplates.models.FlowSession
        fields = [
            "id",
            "registration",
            "registration_details",
            "flow",
            "flow_name",
            "current_node_id",
            "context_data",
            "history",
            "error_details",
            "status",
            "created_at",
            "last_interaction",
        ]
        read_only_fields = ["id", "created_at", "last_interaction"]

    def get_registration_details(self, obj):
        try:
            # Safely resolve the registration object
            reg = obj.registration
            if not reg: return None
            
            # Extract guest name with multiple fallbacks
            g_name = "-"
            if hasattr(reg, 'guest') and reg.guest:
                g_name = reg.guest.name
            elif hasattr(reg, 'name_on_message') and reg.name_on_message:
                g_name = reg.name_on_message
            
            # Extract phone with fallback
            g_phone = "-"
            if hasattr(reg, 'guest') and reg.guest and reg.guest.phone:
                g_phone = reg.guest.phone
                
            return {
                "guest_name": g_name,
                "guest_phone": g_phone,
                "rsvp_status": reg.rsvp_status or "Not Responded",
                "event_name": reg.event.name if reg.event else "Unknown Event",
            }
        except Exception as e:
            import logging
            logger = logging.getLogger("django")
            logger.warning(f"[SERIALIZER-ERROR] FlowSession details resolution failed: {e}")
            return {
                "guest_name": "Error resolving name",
                "guest_phone": "-",
                "rsvp_status": "-",
                "event_name": "-",
            }
