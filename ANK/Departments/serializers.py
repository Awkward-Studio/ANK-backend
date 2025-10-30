from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    BudgetLineItem,
    BudgetFieldPermission,
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
    "payment_status",
    "payment_due_date",
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
            "payment_status",
            "payment_due_date",
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
