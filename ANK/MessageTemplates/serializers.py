from rest_framework import serializers
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
    """

    phone_number_id = serializers.CharField(
        max_length=100, required=True, help_text="Phone Number ID from Meta"
    )
    asset_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    waba_id = serializers.CharField(
        max_length=100, required=True, help_text="WABA ID"
    )
    access_token = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Access token (will be encrypted)",
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
        """
        access_token = validated_data.pop("access_token")
        waba_id = validated_data.get("waba_id")
        phone_number_id = validated_data.get("phone_number_id")

        # Get or create WABA
        waba, created = WhatsAppBusinessAccount.objects.get_or_create(
            waba_id=waba_id,
            defaults={
                "name": validated_data.get("verified_name", f"WABA {waba_id}"),
                "is_active": True,
            },
        )

        # Store token at WABA level (permanent system token)
        try:
            waba.set_token(access_token)
            waba.save()
        except Exception as e:
            raise serializers.ValidationError(
                {"access_token": f"Failed to encrypt token: {str(e)}"}
            )

        # Create or update phone number
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

        return phone
