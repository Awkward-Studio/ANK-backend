from rest_framework import serializers
from Departments.models import EventDepartment
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
    PostEventAdjustmentRevision,
    AllocationDailyMeal,
    ManpowerSettings,
    Skill,
)
from Staff.serializers import UserSerializer


class EventDepartmentField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        department = value.department
        return {
            "id": str(value.id),
            "event": str(value.event_id),
            "department": str(value.department_id),
            "display_name": value.display_name or department.name,
            "department_name": department.name,
            "name": department.name,
        }


class EventDepartmentModelSerializer(serializers.ModelSerializer):
    event_department = EventDepartmentField(queryset=EventDepartment.objects.all())


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = "__all__"


class FreelancerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    skill_names = serializers.SerializerMethodField()
    skills = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), required=False
    )

    def get_skill_names(self, obj):
        return [s.name for s in obj.skills.all()]

    def validate_email(self, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    class Meta:
        model = Freelancer
        fields = [
            "id", "name", "first_name", "title", "skills", "skill_names", "skill_category", "city", "address",
            "parent_name", "id_type", "id_number",
            "bank_account_name", "bank_name", "bank_account_number",
            "bank_branch", "bank_ifsc", "contact_phone", "email",
            "base_daily_rate", "documents", "average_rating", "is_active",
            "created_at", "updated_at"
        ]

class EventCostSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCostSheet
        fields = "__all__"
        read_only_fields = ["total_estimated_cost"]


class ManpowerRequirementSerializer(EventDepartmentModelSerializer):
    skill_name = serializers.ReadOnlyField(source="skill.name")
    team = serializers.CharField(source="teams", read_only=True)

    class Meta:
        model = ManpowerRequirement
        fields = "__all__"



class PostEventAdjustmentRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostEventAdjustmentRevision
        fields = "__all__"


class ManpowerSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManpowerSettings
        fields = "__all__"


class AllocationDailyMealSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllocationDailyMeal
        fields = "__all__"


class PostEventAdjustmentSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="allocation.freelancer.name")
    event_name = serializers.ReadOnlyField(source="allocation.event_department.event.name")
    invoice_status = serializers.ReadOnlyField(source="invoice_workflow.status")
    invoice_token = serializers.SerializerMethodField()
    allocation_is_rated = serializers.ReadOnlyField(source="allocation.is_rated")
    planned_rate = serializers.ReadOnlyField(source="allocation.cost_sheet.negotiated_rate")
    revisions = PostEventAdjustmentRevisionSerializer(many=True, read_only=True)
    actual_meal_allowance = serializers.ReadOnlyField()

    def get_invoice_token(self, obj):
        if hasattr(obj, 'invoice_workflow'):
            return obj.invoice_workflow.secure_token
        return None

    class Meta:
        model = PostEventAdjustment
        fields = "__all__"
        read_only_fields = ["revised_total", "actual_meal_allowance"]


class FreelancerAllocationSerializer(EventDepartmentModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="freelancer.name")
    team = serializers.CharField(source="teams", read_only=True)
    rating_score = serializers.SerializerMethodField()

    def get_rating_score(self, obj):
        from .models import FreelancerRating
        r = FreelancerRating.objects.filter(freelancer=obj.freelancer, event=obj.event_department.event).first()
        return r.score if r else None
    allocation_id = serializers.ReadOnlyField(source="adjustment.allocation.id")
    skill_category = serializers.ReadOnlyField(source="freelancer.skill_category")
    event_name = serializers.ReadOnlyField(source="event_department.event.name")
    mou_status = serializers.SerializerMethodField()
    mou_token = serializers.SerializerMethodField()
    cost_sheet = EventCostSheetSerializer(read_only=True)
    adjustment = PostEventAdjustmentSerializer(read_only=True)
    daily_meals = AllocationDailyMealSerializer(many=True, read_only=True)
    total_meal_allowance = serializers.ReadOnlyField()

    class Meta:
        model = FreelancerAllocation
        fields = [
            "id",
            "freelancer",
            "freelancer_name",
            "teams",
            "team",
            "profile",
            "location",
            "title",
            "first_name",
            "skill_category",
            "event_department",
            "requirement",
            "status",
            "role_description",
            "event_name",
            "start_date",
            "end_date",
            "is_extra",
            "is_adjustment_editable",
            "mou_status",
            "mou_token",
            "assigned_by",
            "cost_sheet",
            "adjustment",
            "daily_meals",
            "total_meal_allowance",
            "is_rated",
            "allocation_id",
            "rating_score",
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
            "created_at",
        ]
        read_only_fields = ["secure_token", "accepted_at"]


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
    rating_score = serializers.SerializerMethodField()

    def get_rating_score(self, obj):
        from .models import FreelancerRating
        r = FreelancerRating.objects.filter(freelancer=obj.freelancer, event=obj.event_department.event).first()
        return r.score if r else None
    allocation_id = serializers.ReadOnlyField(source="adjustment.allocation.id")

    class Meta:
        model = InvoiceWorkflow
        fields = "__all__"
        read_only_fields = ["secure_token", "approved_at", "payable_at", "paid_at", "created_at", "updated_at"]


class ManpowerAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source="actor.name")

    class Meta:
        model = ManpowerAuditLog
        fields = "__all__"
