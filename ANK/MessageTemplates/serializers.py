from rest_framework import serializers
from MessageTemplates.models import MessageTemplate, MessageTemplateVariable

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
