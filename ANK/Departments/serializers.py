from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    BudgetLineItem,
    BudgetFieldPermission,
    ModelPermission,
    DepartmentModelAccess,
)

User = get_user_model()

BUDGET_FIELD_KEYS = {
    "category",
    "sub_category",
    "description",
    "sub_event",
    "function_name",
    "venue",
    "quantity",
    "unit",
    "shifts_or_days",
    "unit_rate",
    "tax_rate_pct",
    "markup_mode",
    "markup_value",
    "advance_amount",
    "balance_amount",
    "vendor_name",
    "invoice",
    "approval_status",
    "payment_status",
    "payment_due_date",
    "exchange_rate_to_inr",
    "remarks",
    "currency",
    "is_active",
}


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "slug", "created_at", "updated_at"]


class EventDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventDepartment
        fields = [
            "id",
            "event",
            "department",
            "display_name",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        event = attrs.get("event") or getattr(self.instance, "event", None)
        dept = attrs.get("department") or getattr(self.instance, "department", None)
        if event and dept:
            qs = EventDepartment.objects.filter(event=event, department=dept)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "This department is already added to the event."
                )
        return attrs


class EventDepartmentStaffAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventDepartmentStaffAssignment
        fields = [
            "id",
            "event_department",
            "user",
            "role",
            "assigned_on",
            "removed_on",
            "created_at",
            "updated_at",
        ]


class BudgetLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetLineItem
        fields = [
            "id",
            "event_department",
            "category",
            "sub_category",
            "description",
            "sub_event",
            "function_name",
            "venue",
            "quantity",
            "unit",
            "shifts_or_days",
            "unit_rate",
            "tax_rate_pct",
            "markup_mode",
            "markup_value",
            "advance_amount",
            "balance_amount",
            "vendor_name",
            "invoice",
            "approval_status",
            "payment_status",
            "payment_due_date",
            "exchange_rate_to_inr",
            "remarks",
            "currency",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        markup_mode = attrs.get("markup_mode") or getattr(
            self.instance, "markup_mode", "none"
        )
        if markup_mode == "none":
            attrs["markup_value"] = None

        for fld in (
            "quantity",
            "shifts_or_days",
            "unit_rate",
            "tax_rate_pct",
            "advance_amount",
            "balance_amount",
        ):
            if fld in attrs and attrs[fld] is not None:
                try:
                    if Decimal(str(attrs[fld])) < 0:
                        raise serializers.ValidationError({fld: "Must be >= 0"})
                except Exception:
                    raise serializers.ValidationError({fld: "Invalid decimal"})
        return attrs


class BudgetFieldPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetFieldPermission
        fields = [
            "id",
            "user",
            "event_department",
            "field_key",
            "created_at",
            "updated_at",
        ]

    def validate_field_key(self, value: str):
        if value not in BUDGET_FIELD_KEYS:
            raise serializers.ValidationError("Invalid field_key.")
        return value


class EventRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class DepartmentRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class EventDepartmentRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event = EventRefSerializer()
    department = DepartmentRefSerializer()


class UserEventDepartmentFieldAccessSerializer(serializers.Serializer):
    event_department = EventDepartmentRefSerializer()
    role = serializers.CharField()
    field_keys = serializers.ListField(child=serializers.CharField(), allow_empty=True)


# ─────────────────────────────────────────────────────────────
# RBAC Permission Serializers
# ─────────────────────────────────────────────────────────────


class ModelPermissionSerializer(serializers.ModelSerializer):
    """Serializer for ModelPermission - field-level permissions."""
    content_type_model = serializers.CharField(source='content_type.model', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    event_department_display = serializers.CharField(source='event_department.display_name', read_only=True)
    
    class Meta:
        model = ModelPermission
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "event_department",
            "event_department_display",
            "content_type",
            "content_type_model",
            "field_name",
            "permission_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate(self, attrs):
        """Validate that the field exists on the model."""
        content_type = attrs.get('content_type') or getattr(self.instance, 'content_type', None)
        field_name = attrs.get('field_name') or getattr(self.instance, 'field_name', None)
        
        if content_type and field_name:
            model_class = content_type.model_class()
            if model_class:
                from Departments.models import get_model_fields
                valid_fields = get_model_fields(model_class)
                if field_name not in valid_fields:
                    raise serializers.ValidationError(
                        f"Field '{field_name}' does not exist on {model_class.__name__}"
                    )
        return attrs


class DepartmentModelAccessSerializer(serializers.ModelSerializer):
    """Serializer for DepartmentModelAccess - department-to-model mapping."""
    department_name = serializers.CharField(source='department.name', read_only=True)
    content_type_model = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = DepartmentModelAccess
        fields = [
            "id",
            "department",
            "department_name",
            "content_type",
            "content_type_model",
            "can_read",
            "can_write",
            "can_create",
            "can_delete",
        ]
        read_only_fields = ["id"]
