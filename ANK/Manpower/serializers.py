from rest_framework import serializers
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    FreelancerRating,
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


class FreelancerAllocationSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.ReadOnlyField(source="freelancer.name")
    skill_category = serializers.ReadOnlyField(source="freelancer.skill_category")
    cost_sheet = EventCostSheetSerializer(read_only=True)

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
            "assigned_by",
            "cost_sheet",
            "created_at",
            "updated_at",
        ]


class MoUSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoU
        fields = [
            "id",
            "allocation",
            "status",
            "template_data",
            "accepted_at",
            "signed_pdf",
            "created_at",
        ]
        read_only_fields = ["secure_token", "accepted_at", "signed_pdf"]


class PostEventAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostEventAdjustment
        fields = "__all__"
        read_only_fields = ["revised_total"]


class FreelancerRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerRating
        fields = "__all__"
