from rest_framework import serializers
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    FreelancerRating,
    EventManpowerLock,
    InvoiceWorkflow,
    ManpowerAuditLog,
)
from Staff.serializers import UserSerializer


class FreelancerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Freelancer
        fields = "__all__"


class EventCostSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCostSheet
        fields = "__all__"
        read_only_fields = ["total_estimated_cost"]


class ManpowerRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManpowerRequirement
        fields = "__all__"


class PostEventAdjustmentSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="allocation.freelancer.name")
    event_name = serializers.ReadOnlyField(source="allocation.event_department.event.name")
    invoice_status = serializers.ReadOnlyField(source="invoice.status")
    allocation_is_rated = serializers.ReadOnlyField(source="allocation.is_rated")

    class Meta:
        model = PostEventAdjustment
        fields = "__all__"
        read_only_fields = ["revised_total"]


class FreelancerAllocationSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="freelancer.name")
    skill_category = serializers.ReadOnlyField(source="freelancer.skill_category")
    event_name = serializers.ReadOnlyField(source="event_department.event.name")
    mou_status = serializers.SerializerMethodField()
    mou_token = serializers.SerializerMethodField()
    cost_sheet = EventCostSheetSerializer(read_only=True)
    adjustment = PostEventAdjustmentSerializer(read_only=True)

    class Meta:
        model = FreelancerAllocation
        fields = [
            "id",
            "freelancer",
            "freelancer_name",
            "skill_category",
            "event_department",
            "status",
            "role_description",
            "event_name",
            "start_date",
            "end_date",
            "is_adjustment_editable",
            "mou_status",
            "mou_token",
            "assigned_by",
            "cost_sheet",
            "adjustment",
            "is_rated",
            "created_at",
            "updated_at",
        ]

    def get_mou_status(self, obj):
        mou = obj.mous.order_by("-created_at").first()
        return mou.status if mou else None

    def get_mou_token(self, obj):
        mou = obj.mous.order_by("-created_at").first()
        return mou.secure_token if mou else None


class MoUSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="allocation.freelancer.name")
    event_name = serializers.ReadOnlyField(source="allocation.event_department.event.name")

    class Meta:
        model = MoU
        fields = [
            "id",
            "allocation",
            "freelancer_name",
            "event_name",
            "status",
            "secure_token",
            "template_data",
            "expires_at",
            "access_code",
            "accepted_at",
            "signed_pdf",
            "created_at",
        ]
        read_only_fields = ["secure_token", "accepted_at", "signed_pdf"]


class FreelancerRatingSerializer(serializers.ModelSerializer):
    event_name = serializers.ReadOnlyField(source="event.name")
    
    class Meta:
        model = FreelancerRating
        fields = "__all__"


class EventManpowerLockSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventManpowerLock
        fields = "__all__"
        read_only_fields = [
            "locked_by",
            "locked_at",
            "unlocked_by",
            "unlocked_at",
            "created_at",
            "updated_at",
        ]


class InvoiceWorkflowSerializer(serializers.ModelSerializer):
    event_name = serializers.ReadOnlyField(source="event.name")
    department_name = serializers.ReadOnlyField(source="event_department.department.name")
    freelancer_name = serializers.ReadOnlyField(source="freelancer.name")

    class Meta:
        model = InvoiceWorkflow
        fields = "__all__"
        read_only_fields = ["approved_at", "payable_at", "paid_at", "created_at", "updated_at"]


class ManpowerAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source="actor.name")

    class Meta:
        model = ManpowerAuditLog
        fields = "__all__"
