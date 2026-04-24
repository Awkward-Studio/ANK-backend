from django.contrib import admin
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    FreelancerRating,
    AllocationDailyMeal,
    ManpowerSettings,
)


@admin.register(Freelancer)
class FreelancerAdmin(admin.ModelAdmin):
    list_display = ("name", "skill_category", "city", "average_rating", "is_active")
    search_fields = ("name", "email", "skill_category")
    list_filter = ("is_active", "skill_category", "city")


@admin.register(ManpowerRequirement)
class ManpowerRequirementAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "skill_category",
        "quantity_required",
        "event_department",
        "status",
    )
    list_filter = ("status", "skill_category")
    search_fields = ("name", "skill_category", "event_department__department__name")


class EventCostSheetInline(admin.StackedInline):
    model = EventCostSheet
    can_delete = False


class AllocationDailyMealInline(admin.TabularInline):
    model = AllocationDailyMeal
    extra = 0


@admin.register(FreelancerAllocation)
class FreelancerAllocationAdmin(admin.ModelAdmin):
    list_display = ("freelancer", "event_department", "status", "assigned_by")
    list_filter = ("status", "event_department")
    inlines = [EventCostSheetInline, AllocationDailyMealInline]


@admin.register(ManpowerSettings)
class ManpowerSettingsAdmin(admin.ModelAdmin):
    list_display = ("default_breakfast_rate", "default_lunch_rate", "default_dinner_rate", "updated_at")

    def has_add_permission(self, request):
        return not ManpowerSettings.objects.exists()


@admin.register(EventCostSheet)
class EventCostSheetAdmin(admin.ModelAdmin):
    list_display = ("allocation", "negotiated_rate", "total_estimated_cost")


@admin.register(MoU)
class MoUAdmin(admin.ModelAdmin):
    list_display = ("allocation", "status", "accepted_at")
    list_filter = ("status",)
    readonly_fields = ("secure_token",)


@admin.register(PostEventAdjustment)
class PostEventAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("allocation", "actual_days_worked", "admin_approval_status")
    list_filter = ("admin_approval_status",)


@admin.register(FreelancerRating)
class FreelancerRatingAdmin(admin.ModelAdmin):
    list_display = ("freelancer", "event", "score", "rated_by")
    list_filter = ("score",)
