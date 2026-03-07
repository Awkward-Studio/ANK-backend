import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework import status, filters
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, F, Avg, Q
from django.db import transaction
from django.http import HttpResponse, Http404
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font
from django_filters.rest_framework import DjangoFilterBackend
from Departments.mixins import DepartmentAccessMixin
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)
from .models import (
    Freelancer,
    ManpowerRequirement,
    FreelancerAllocation,
    EventCostSheet,
    MoU,
    PostEventAdjustment,
    PostEventAdjustmentRevision,
    FreelancerRating,
    EventManpowerLock,
    InvoiceWorkflow,
    ManpowerAuditLog,
    AllocationDailyMeal,
    ManpowerSettings,
)
from .serializers import (
    FreelancerSerializer,
    ManpowerRequirementSerializer,
    FreelancerAllocationSerializer,
    EventCostSheetSerializer,
    MoUSerializer,
    PostEventAdjustmentSerializer,
    FreelancerRatingSerializer,
    EventManpowerLockSerializer,
    InvoiceWorkflowSerializer,
    ManpowerAuditLogSerializer,
    AllocationDailyMealSerializer,
    ManpowerSettingsSerializer,
)

ADMIN_ROLES = {"admin", "super_admin"}


def _has_any_role(request, allowed_roles):
    return getattr(request.user, "role", None) in allowed_roles


def _require_role(request, allowed_roles):
    if not _has_any_role(request, allowed_roles):
        return Response(
            {"detail": "You do not have permission to perform this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _get_accounts_event_ids_for_user(user):
    from Departments.models import EventDepartment

    if user.role in ADMIN_ROLES:
        return None  # Global access

    # Department heads of Accounts get access across all Accounts event-departments.
    if user.role == "department_head" and user.department and user.department.slug == "accounts":
        return set(
            EventDepartment.objects.filter(department__slug="accounts").values_list(
                "event_id", flat=True
            )
        )

    # Staff get access via explicit event-department assignment in Accounts department.
    return set(
        EventDepartment.objects.filter(
            department__slug="accounts",
            staff_assignments__user=user,
        ).values_list("event_id", flat=True)
    )


def _filter_to_accounts_scope(request, qs, event_field):
    event_ids = _get_accounts_event_ids_for_user(request.user)
    if event_ids is None:
        return qs
    if not event_ids:
        return qs.none()
    return qs.filter(**{f"{event_field}__in": event_ids})


def _require_accounts_access(request):
    if request.user.role in ADMIN_ROLES:
        return None
    event_ids = _get_accounts_event_ids_for_user(request.user)
    if event_ids:
        return None
    return Response(
        {"detail": "Accounts department assignment required."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _can_manage_manpower_event(user, event_id):
    from Departments.models import EventDepartment

    if user.role in ADMIN_ROLES:
        return True

    if user.role == "department_head" and user.department and user.department.slug == "accounts":
        return EventDepartment.objects.filter(
            event_id=event_id, department__slug="accounts"
        ).exists()

    if user.role == "staff":
        return EventDepartment.objects.filter(
            event_id=event_id,
            department__slug="accounts",
            staff_assignments__user=user,
        ).exists()

    return False


def _require_manpower_event_access(request, event_id):
    if _can_manage_manpower_event(request.user, event_id):
        return None
    return Response(
        {"detail": "Accounts event-department assignment required for this event."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _event_id_from_event_department_id(event_department_id):
    from Departments.models import EventDepartment

    if not event_department_id:
        return None
    event_department = EventDepartment.objects.select_related("event").filter(
        id=event_department_id
    ).first()
    return getattr(event_department, "event_id", None)


def _is_event_locked(event_id):
    if not event_id:
        return False
    lock = EventManpowerLock.objects.filter(event_id=event_id).first()
    return bool(lock and lock.is_locked)


def _check_lock_or_override(request, event_id):
    if not _is_event_locked(event_id):
        return None

    is_admin = _has_any_role(request, ADMIN_ROLES)
    override = bool(request.data.get("admin_override")) if hasattr(request, "data") else False
    if is_admin and override:
        return None

    return Response(
        {
            "detail": "Manpower changes are locked for this event.",
            "event_id": str(event_id),
            "requires_admin_override": True,
        },
        status=status.HTTP_423_LOCKED,
    )


def _log_action(request, action, target_obj, event_id=None, details=None):
    try:
        ManpowerAuditLog.objects.create(
            event_id=event_id,
            actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            action=action,
            target_model=target_obj.__class__.__name__,
            target_id=str(target_obj.pk),
            details=details or {},
        )
    except Exception:
        # Avoid failing business flow due to audit logging issues.
        pass

def _create_revision(adjustment, action_type, user=None, comments=""):
    try:
        PostEventAdjustmentRevision.objects.create(
            adjustment=adjustment,
            action_type=action_type,
            actor=user if user and user.is_authenticated else None,
            actor_name=user.name if user and user.is_authenticated else adjustment.allocation.freelancer.name,
            actual_days_worked=adjustment.actual_days_worked,
            total_engagement_days=adjustment.total_engagement_days,
            engagement_periods=adjustment.engagement_periods,
            travel_adjustments=adjustment.travel_adjustments,
            other_adjustments=adjustment.other_adjustments,
            override_negotiated_rate=adjustment.override_negotiated_rate,
            revised_total=adjustment.revised_total,
            comments=comments or adjustment.freelancer_comments
        )
    except Exception:
        pass



@document_api_view(
    {
        "get": doc_list(
            response=FreelancerSerializer(many=True),
            parameters=[
                query_param("skill_category", "str", False, "Filter by skill category"),
                query_param("city", "str", False, "Filter by city"),
                query_param("search", "str", False, "Search by name, email, or phone"),
            ],
            description="List all active freelancers",
            tags=["Manpower: Freelancers"],
        ),
        "post": doc_create(
            request=FreelancerSerializer,
            response=FreelancerSerializer,
            description="Create a new freelancer",
            tags=["Manpower: Freelancers"],
        ),
    }
)
class FreelancerList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        try:
            qs = Freelancer.objects.filter(is_active=True)
            
            # Filtering
            skill = request.query_params.get("skill_category")
            city = request.query_params.get("city")
            search = request.query_params.get("search")
            
            if skill:
                qs = qs.filter(skill_category=skill)
            if city:
                qs = qs.filter(city=city)
            if search:
                qs = qs.filter(
                    Q(name__icontains=search)
                    | Q(email__icontains=search)
                    | Q(contact_phone__icontains=search)
                )
            
            # Ordering
            ordering = request.query_params.get("ordering")
            if ordering:
                qs = qs.order_by(ordering)
            else:
                qs = qs.order_by("name")

            return Response(FreelancerSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching freelancers", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        try:
            ser = FreelancerSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(request, "freelancer_created", obj, details={"name": obj.name})
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerSerializer,
            description="Retrieve a freelancer by ID",
            tags=["Manpower: Freelancers"],
        ),
        "put": doc_update(
            request=FreelancerSerializer,
            response=FreelancerSerializer,
            description="Update a freelancer by ID",
            tags=["Manpower: Freelancers"],
        ),
        "delete": doc_destroy(description="Deactivate a freelancer", tags=["Manpower: Freelancers"]),
    }
)
class FreelancerDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            return Response(FreelancerSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            ser = FreelancerSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            _log_action(request, "freelancer_updated", updated, details={"name": updated.name})
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        try:
            obj = get_object_or_404(Freelancer, pk=pk)
            obj.is_active = False
            obj.save()
            _log_action(request, "freelancer_deactivated", obj, details={"name": obj.name})
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deactivating freelancer", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=ManpowerRequirementSerializer(many=True),
            parameters=[
                query_param("event_department", "uuid", False, "Filter by event department ID"),
                query_param("status", "str", False, "Filter by status"),
                query_param("skill_category", "str", False, "Filter by skill category"),
            ],
            description="List manpower requirements",
            tags=["Manpower: Requirements"],
        ),
        "post": doc_create(
            request=ManpowerRequirementSerializer,
            response=ManpowerRequirementSerializer,
            description="Create a manpower requirement",
            tags=["Manpower: Requirements"],
        ),
    }
)
class ManpowerRequirementList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return ManpowerRequirement.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "event_department__event_id")
            
            ed = request.query_params.get("event_department")
            stat = request.query_params.get("status")
            skill = request.query_params.get("skill_category")
            
            if ed:
                qs = qs.filter(event_department_id=ed)
            if stat:
                qs = qs.filter(status=stat)
            if skill:
                qs = qs.filter(skill_category=skill)
                
            return Response(ManpowerRequirementSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching requirements", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        event_id = _event_id_from_event_department_id(request.data.get("event_department"))
        denied = _require_manpower_event_access(request, event_id)
        if denied:
            return denied
        try:
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = ManpowerRequirementSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(
                request,
                "requirement_created",
                obj,
                event_id=event_id,
                details={"skill_category": obj.skill_category, "quantity_required": obj.quantity_required},
            )
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=ManpowerRequirementSerializer,
            description="Retrieve a manpower requirement by ID",
            tags=["Manpower: Requirements"],
        ),
        "put": doc_update(
            request=ManpowerRequirementSerializer,
            response=ManpowerRequirementSerializer,
            description="Update a manpower requirement by ID",
            tags=["Manpower: Requirements"],
        ),
        "delete": doc_destroy(description="Delete a manpower requirement", tags=["Manpower: Requirements"]),
    }
)
class ManpowerRequirementDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return ManpowerRequirement.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.event_department.event_id)
            if denied:
                return denied
            return Response(ManpowerRequirementSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = ManpowerRequirementSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            _log_action(request, "requirement_updated", updated, event_id=event_id)
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            obj.delete()
            _log_action(request, "requirement_deleted", obj, event_id=event_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting requirement", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=FreelancerAllocationSerializer(many=True),
            parameters=[
                query_param("event_department", "uuid", False, "Filter by event department ID"),
                query_param("freelancer", "uuid", False, "Filter by freelancer ID"),
                query_param("status", "str", False, "Filter by status"),
            ],
            description="List freelancer allocations",
            tags=["Manpower: Allocations"],
        ),
        "post": doc_create(
            request=FreelancerAllocationSerializer,
            response=FreelancerAllocationSerializer,
            description="Create a freelancer allocation",
            tags=["Manpower: Allocations"],
        ),
    }
)
class FreelancerAllocationList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerAllocation.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "event_department__event_id")
            
            ed = request.query_params.get("event_department")
            free = request.query_params.get("freelancer")
            stat = request.query_params.get("status")
            
            if ed:
                qs = qs.filter(event_department_id=ed)
            if free:
                qs = qs.filter(freelancer_id=free)
            if stat:
                qs = qs.filter(status=stat)
                
            return Response(FreelancerAllocationSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocations", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        event_id = _event_id_from_event_department_id(request.data.get("event_department"))
        denied = _require_manpower_event_access(request, event_id)
        if denied:
            return denied
        try:
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = FreelancerAllocationSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(request, "allocation_created", obj, event_id=event_id, details={"status": obj.status})
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerAllocationSerializer,
            description="Retrieve a freelancer allocation by ID",
            tags=["Manpower: Allocations"],
        ),
        "put": doc_update(
            request=FreelancerAllocationSerializer,
            response=FreelancerAllocationSerializer,
            description="Update a freelancer allocation by ID",
            tags=["Manpower: Allocations"],
        ),
        "delete": doc_destroy(description="Delete a freelancer allocation", tags=["Manpower: Allocations"]),
    }
)
class FreelancerAllocationDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerAllocation.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.event_department.event_id)
            if denied:
                return denied
            return Response(FreelancerAllocationSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = FreelancerAllocationSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            _log_action(request, "allocation_updated", updated, event_id=event_id, details={"status": updated.status})
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, pk):
        """
        Handles bulk updates or toggles based on the action in the request.
        """
        if "bulk-update-meals" in request.path:
            return self.bulk_update_meals(request, pk)
        if "toggle-work-day" in request.path:
            return self.toggle_work_day(request, pk)
        if "update-meal" in request.path:
            return self.update_meal(request, pk)
        return Response({"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update_meal(self, request, pk=None):
        """
        Updates a specific meal's types.
        Expects: { "meal_id": "<uuid>", "breakfast_type": "...", "lunch_type": "...", "dinner_type": "..." }
        """
        try:
            allocation = get_object_or_404(FreelancerAllocation, pk=pk)
            event_id = allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
                
            meal_id = request.data.get("meal_id")
            if not meal_id:
                return Response({"detail": "meal_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            meal = get_object_or_404(AllocationDailyMeal, pk=meal_id, allocation=allocation)
            
            if "breakfast_type" in request.data:
                meal.breakfast_type = request.data["breakfast_type"]
            if "lunch_type" in request.data:
                meal.lunch_type = request.data["lunch_type"]
            if "dinner_type" in request.data:
                meal.dinner_type = request.data["dinner_type"]
                
            meal.save()
            
            if hasattr(allocation, "cost_sheet"):
                allocation.cost_sheet.save()
                
            return Response(AllocationDailyMealSerializer(meal).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating meal", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def bulk_update_meals(self, request, pk=None):
        """
        Bulk updates meal types for an allocation.
        Expects: { "meal_type": "breakfast"|"lunch"|"dinner", "action_type": "crew_meal"|"allowance" }
        """
        try:
            allocation = get_object_or_404(FreelancerAllocation, pk=pk)
            event_id = allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            
            meal_type = request.data.get("meal_type")  # breakfast, lunch, dinner
            action_type = request.data.get("action_type")  # crew_meal, allowance
            
            if meal_type not in ["breakfast", "lunch", "dinner"]:
                return Response({"detail": "Invalid meal_type. Must be 'breakfast', 'lunch', or 'dinner'."}, status=status.HTTP_400_BAD_REQUEST)
            if action_type not in ["crew_meal", "allowance"]:
                return Response({"detail": "Invalid action_type. Must be 'crew_meal' or 'allowance'."}, status=status.HTTP_400_BAD_REQUEST)
                
            meals = AllocationDailyMeal.objects.filter(allocation=allocation)
            updated_count = 0
            for meal in meals:
                setattr(meal, f"{meal_type}_type", action_type)
                meal.save()
                updated_count += 1
                
            if hasattr(allocation, "cost_sheet"):
                allocation.cost_sheet.save()
            
            _log_action(
                request,
                "allocation_meals_bulk_updated",
                allocation,
                event_id=event_id,
                details={"meal_type": meal_type, "action_type": action_type, "updated_count": updated_count},
            )
            return Response({
                "status": "bulk update successful",
                "updated_count": updated_count,
                "total_meal_allowance": str(allocation.total_meal_allowance),
            })
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating meals", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def toggle_work_day(self, request, pk=None):
        """
        Toggles is_worked for a specific day.
        Expects: { "meal_id": "<uuid>" }
        """
        try:
            allocation = get_object_or_404(FreelancerAllocation, pk=pk)
            event_id = allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
                
            meal_id = request.data.get("meal_id")
            if not meal_id:
                return Response({"detail": "meal_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
            meal = get_object_or_404(AllocationDailyMeal, pk=meal_id, allocation=allocation)
            meal.is_worked = not meal.is_worked
            meal.save()
            
            # Sync PostEventAdjustment's actual_days_worked
            if hasattr(allocation, "adjustment"):
                worked_days = allocation.daily_meals.filter(is_worked=True).count()
                allocation.adjustment.actual_days_worked = Decimal(str(worked_days))
                allocation.adjustment.save()
            
            _log_action(
                request,
                "allocation_work_day_toggled",
                allocation,
                event_id=event_id,
                details={"meal_id": str(meal_id), "date": str(meal.date), "is_worked": meal.is_worked},
            )
            return Response({
                "is_worked": meal.is_worked,
                "date": str(meal.date),
                "actual_days_worked": allocation.daily_meals.filter(is_worked=True).count(),
            })
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error toggling work day", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            obj.delete()
            _log_action(request, "allocation_deleted", obj, event_id=event_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting allocation", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_allocation(request, pk):
    """Confirm a freelancer allocation."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        denied = _require_manpower_event_access(request, allocation.event_department.event_id)
        if denied:
            return denied
        lock_error = _check_lock_or_override(request, allocation.event_department.event_id)
        if lock_error:
            return lock_error
        allocation.status = "confirmed"
        allocation.save()
        _log_action(
            request,
            "allocation_confirmed",
            allocation,
            event_id=allocation.event_department.event_id,
            details={"status": "confirmed"},
        )
        return Response({"status": "confirmed"})
    except Http404:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response(
            {"detail": "Error confirming allocation", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def release_allocation(request, pk):
    """Release a freelancer allocation."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        denied = _require_manpower_event_access(request, allocation.event_department.event_id)
        if denied:
            return denied
        lock_error = _check_lock_or_override(request, allocation.event_department.event_id)
        if lock_error:
            return lock_error
        allocation.status = "released"
        allocation.save()
        _log_action(
            request,
            "allocation_released",
            allocation,
            event_id=allocation.event_department.event_id,
            details={"status": "released"},
        )
        return Response({"status": "released"})
    except Http404:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response(
            {"detail": "Error releasing allocation", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_mou(request, pk):
    """Generate or update MoU for an allocation and transition it to sent."""
    try:
        allocation = get_object_or_404(FreelancerAllocation, pk=pk)
        denied = _require_manpower_event_access(request, allocation.event_department.event_id)
        if denied:
            return denied
        lock_error = _check_lock_or_override(request, allocation.event_department.event_id)
        if lock_error:
            return lock_error
        mou, created = MoU.objects.get_or_create(
            allocation=allocation,
            defaults={"status": "draft", "template_data": {"terms": "Standard MoU terms..."}}
        )
        
        # Reset to sent if it was draft or rejected
        if mou.status in ["draft", "rejected"]:
            if not getattr(mou, "expires_at", None) or mou.status == "rejected":
                mou.expires_at = timezone.now() + timedelta(days=7)
            mou.status = "sent"
            mou.save()
            
        _log_action(
            request,
            "mou_generated",
            mou,
            event_id=allocation.event_department.event_id,
            details={"allocation_id": str(allocation.id), "status": mou.status},
        )
        return Response({
            "status": mou.status,
            "mou_id": mou.id,
            "secure_token": str(mou.secure_token),
            "secure_link": f"/mou/{mou.secure_token}"
        })
    except Http404:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response(
            {"detail": "Error generating MoU", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_api_view(
    {
        "get": doc_list(
            response=EventCostSheetSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("budget_item", "uuid", False, "Filter by budget item ID"),
            ],
            description="List cost sheets",
            tags=["Manpower: Cost Sheets"],
        ),
        "post": doc_create(
            request=EventCostSheetSerializer,
            response=EventCostSheetSerializer,
            description="Create a cost sheet",
            tags=["Manpower: Cost Sheets"],
        ),
    }
)
class EventCostSheetList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return EventCostSheet.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "allocation__event_department__event_id")
            
            alloc = request.query_params.get("allocation")
            budget = request.query_params.get("budget_item")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if budget:
                qs = qs.filter(budget_item_id=budget)
                
            return Response(EventCostSheetSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching cost sheets", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            allocation = FreelancerAllocation.objects.select_related("event_department").filter(
                id=request.data.get("allocation")
            ).first()
            event_id = allocation.event_department.event_id if allocation else None
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = EventCostSheetSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(request, "cost_sheet_created", obj, event_id=event_id)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventCostSheetSerializer,
            description="Retrieve a cost sheet by ID",
            tags=["Manpower: Cost Sheets"],
        ),
        "put": doc_update(
            request=EventCostSheetSerializer,
            response=EventCostSheetSerializer,
            description="Update a cost sheet by ID",
            tags=["Manpower: Cost Sheets"],
        ),
        "delete": doc_destroy(description="Delete a cost sheet", tags=["Manpower: Cost Sheets"]),
    }
)
class EventCostSheetDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return EventCostSheet.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.allocation.event_department.event_id)
            if denied:
                return denied
            return Response(EventCostSheetSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = EventCostSheetSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            _log_action(request, "cost_sheet_updated", updated, event_id=event_id)
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            obj.delete()
            _log_action(request, "cost_sheet_deleted", obj, event_id=event_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting cost sheet", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=MoUSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("status", "str", False, "Filter by status"),
            ],
            description="List MoUs",
            tags=["Manpower: MoUs"],
        ),
        "post": doc_create(
            request=MoUSerializer,
            response=MoUSerializer,
            description="Create an MoU",
            tags=["Manpower: MoUs"],
        ),
    }
)
class MoUList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return MoU.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "allocation__event_department__event_id")
            
            alloc = request.query_params.get("allocation")
            stat = request.query_params.get("status")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if stat:
                qs = qs.filter(status=stat)
                
            return Response(MoUSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching MoUs", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            allocation = FreelancerAllocation.objects.select_related("event_department").filter(
                id=request.data.get("allocation")
            ).first()
            event_id = allocation.event_department.event_id if allocation else None
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            ser = MoUSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(request, "mou_created", obj, event_id=obj.allocation.event_department.event_id)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=MoUSerializer,
            description="Retrieve an MoU by ID",
            tags=["Manpower: MoUs"],
        ),
        "put": doc_update(
            request=MoUSerializer,
            response=MoUSerializer,
            description="Update an MoU by ID",
            tags=["Manpower: MoUs"],
        ),
        "delete": doc_destroy(description="Delete an MoU", tags=["Manpower: MoUs"]),
    }
)
class MoUDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return MoU.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.allocation.event_department.event_id)
            if denied:
                return denied
            return Response(MoUSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.allocation.event_department.event_id)
            if denied:
                return denied
            ser = MoUSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            _log_action(request, "mou_updated", updated, event_id=updated.allocation.event_department.event_id)
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.allocation.event_department.event_id)
            if denied:
                return denied
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting MoU", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=PostEventAdjustmentSerializer(many=True),
            parameters=[
                query_param("allocation", "uuid", False, "Filter by allocation ID"),
                query_param("admin_approval_status", "str", False, "Filter by approval status"),
            ],
            description="List post-event adjustments",
            tags=["Manpower: Adjustments"],
        ),
        "post": doc_create(
            request=PostEventAdjustmentSerializer,
            response=PostEventAdjustmentSerializer,
            description="Create a post-event adjustment",
            tags=["Manpower: Adjustments"],
        ),
    }
)
class PostEventAdjustmentList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return PostEventAdjustment.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "allocation__event_department__event_id")
            
            alloc = request.query_params.get("allocation")
            stat = request.query_params.get("admin_approval_status")
            
            if alloc:
                qs = qs.filter(allocation_id=alloc)
            if stat:
                qs = qs.filter(admin_approval_status=stat)
                
            return Response(PostEventAdjustmentSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching adjustments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            allocation = FreelancerAllocation.objects.select_related("event_department").filter(
                id=request.data.get("allocation")
            ).first()
            event_id = allocation.event_department.event_id if allocation else None
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = PostEventAdjustmentSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            obj = ser.save()
            _log_action(request, "adjustment_created", obj, event_id=event_id)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=PostEventAdjustmentSerializer,
            description="Retrieve a post-event adjustment by ID",
            tags=["Manpower: Adjustments"],
        ),
        "put": doc_update(
            request=PostEventAdjustmentSerializer,
            response=PostEventAdjustmentSerializer,
            description="Update a post-event adjustment by ID",
            tags=["Manpower: Adjustments"],
        ),
        "delete": doc_destroy(description="Delete a post-event adjustment", tags=["Manpower: Adjustments"]),
    }
)
class PostEventAdjustmentDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return PostEventAdjustment.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.allocation.event_department.event_id)
            if denied:
                return denied
            return Response(PostEventAdjustmentSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            ser = PostEventAdjustmentSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            updated = ser.save()
            # If it's being marked as disputed, log it as a dispute revision
            if request.data.get("admin_approval_status") == "disputed":
                _create_revision(updated, "dispute", user=request.user)
            _log_action(request, "adjustment_updated", updated, event_id=event_id)
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            event_id = obj.allocation.event_department.event_id
            denied = _require_manpower_event_access(request, event_id)
            if denied:
                return denied
            lock_error = _check_lock_or_override(request, event_id)
            if lock_error:
                return lock_error
            obj.delete()
            _log_action(request, "adjustment_deleted", obj, event_id=event_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting adjustment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=FreelancerRatingSerializer(many=True),
            parameters=[
                query_param("freelancer", "uuid", False, "Filter by freelancer ID"),
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("score", "int", False, "Filter by score"),
            ],
            description="List freelancer ratings",
            tags=["Manpower: Ratings"],
        ),
        "post": doc_create(
            request=FreelancerRatingSerializer,
            response=FreelancerRatingSerializer,
            description="Create a freelancer rating",
            tags=["Manpower: Ratings"],
        ),
    }
)
class FreelancerRatingList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerRating.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        try:
            qs = _filter_to_accounts_scope(request, self.get_queryset(), "event_id")
            
            free = request.query_params.get("freelancer")
            ev = request.query_params.get("event")
            score = request.query_params.get("score")
            
            if free:
                qs = qs.filter(freelancer_id=free)
            if ev:
                qs = qs.filter(event_id=ev)
            if score:
                qs = qs.filter(score=score)
                
            return Response(FreelancerRatingSerializer(qs, many=True).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching ratings", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        denied = _require_manpower_event_access(request, request.data.get("event"))
        if denied:
            return denied
        try:
            freelancer_id = request.data.get("freelancer")
            event_id = request.data.get("event")
            score = request.data.get("score")
            feedback = request.data.get("feedback", "")

            # Upsert Logic: Prevent duplicates, allow editing
            obj, created = FreelancerRating.objects.update_or_create(
                freelancer_id=freelancer_id,
                event_id=event_id,
                defaults={
                    "score": score,
                    "feedback": feedback,
                    "rated_by": request.user
                }
            )

            # Sync Logic: Mark all allocations for this freelancer in this event as rated
            FreelancerAllocation.objects.filter(
                freelancer_id=freelancer_id,
                event_department__event_id=event_id
            ).update(is_rated=True)

            ser = FreelancerRatingSerializer(obj)
            action = "freelancer_rating_created" if created else "freelancer_rating_updated"
            _log_action(request, action, obj, event_id=obj.event_id, details={"score": score})
            return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error creating rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=FreelancerRatingSerializer,
            description="Retrieve a freelancer rating by ID",
            tags=["Manpower: Ratings"],
        ),
        "put": doc_update(
            request=FreelancerRatingSerializer,
            response=FreelancerRatingSerializer,
            description="Update a freelancer rating by ID",
            tags=["Manpower: Ratings"],
        ),
        "delete": doc_destroy(description="Delete a freelancer rating", tags=["Manpower: Ratings"]),
    }
)
class FreelancerRatingDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return FreelancerRating.objects.all()

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.event_id)
            if denied:
                return denied
            return Response(FreelancerRatingSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.event_id)
            if denied:
                return denied
            ser = FreelancerRatingSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            denied = _require_manpower_event_access(request, obj.event_id)
            if denied:
                return denied
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error deleting rating", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def accounts_summary(request):
    try:
        denied = _require_accounts_access(request)
        if denied:
            return denied
        pending_payments = PostEventAdjustment.objects.filter(
            admin_approval_status="approved"
        ).select_related("allocation__freelancer", "allocation__event_department__event")
        pending_payments = _filter_to_accounts_scope(
            request, pending_payments, "allocation__event_department__event_id"
        )

        event_id = request.query_params.get("event")
        department_id = request.query_params.get("department")
        freelancer_id = request.query_params.get("freelancer")
        status_filter = request.query_params.get("status")

        if event_id:
            pending_payments = pending_payments.filter(allocation__event_department__event_id=event_id)
        if department_id:
            pending_payments = pending_payments.filter(allocation__event_department__department_id=department_id)
        if freelancer_id:
            pending_payments = pending_payments.filter(allocation__freelancer_id=freelancer_id)
        if status_filter:
            pending_payments = pending_payments.filter(admin_approval_status=status_filter)

        event_totals = pending_payments.values(
            event_name=F("allocation__event_department__event__name")
        ).annotate(
            total_liability=Sum("revised_total"),
            freelancer_count=Count("id")
        )

        vendor_liabilities = pending_payments.values(
            vendor_name=F("allocation__freelancer__name")
        ).annotate(
            total_amount=Sum("revised_total"),
            event_count=Count("allocation__event_department__event", distinct=True)
        )

        return Response({
            "pending_payments_count": pending_payments.count(),
            "total_liability": pending_payments.aggregate(Sum("revised_total"))["revised_total__sum"] or 0,
            "event_summaries": list(event_totals),
            "vendor_liabilities": list(vendor_liabilities),
        })
    except Exception as e:
        return Response(
            {"detail": "Error fetching accounts summary", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_accounts_excel(request):
    """
    Export all approved vendor liabilities to an Excel file.
    """
    try:
        denied = _require_accounts_access(request)
        if denied:
            return denied
        # Fetch approved adjustments
        pending_payments = PostEventAdjustment.objects.filter(
            admin_approval_status="approved"
        ).select_related(
            "allocation__freelancer",
            "allocation__event_department__event",
            "allocation__event_department__department"
        ).order_by("allocation__event_department__event__name")
        pending_payments = _filter_to_accounts_scope(
            request, pending_payments, "allocation__event_department__event_id"
        )

        event_id = request.query_params.get("event")
        department_id = request.query_params.get("department")
        freelancer_id = request.query_params.get("freelancer")

        if event_id:
            pending_payments = pending_payments.filter(allocation__event_department__event_id=event_id)
        if department_id:
            pending_payments = pending_payments.filter(allocation__event_department__department_id=department_id)
        if freelancer_id:
            pending_payments = pending_payments.filter(allocation__freelancer_id=freelancer_id)

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Vendor Liabilities"

        # Headers
        headers = [
            "Event Name", "Department", "Freelancer Name", 
            "Actual Days Worked", "Negotiated Rate", "Total Liability"
        ]
        ws.append(headers)
        
        # Style headers
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Data rows
        for adj in pending_payments:
            alloc = adj.allocation
            ws.append([
                alloc.event_department.event.name,
                alloc.event_department.department.name,
                alloc.freelancer.name,
                float(adj.actual_days_worked),
                float(alloc.cost_sheet.negotiated_rate),
                float(adj.revised_total)
            ])

        # Create response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="VendorLiabilities.xlsx"'
        wb.save(response)
        return response

    except Exception as e:
        return Response(
            {"detail": "Error generating Excel report", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lock_event_manpower(request, event_id):
    denied = _require_role(request, ADMIN_ROLES)
    if denied:
        return denied

    lock, _ = EventManpowerLock.objects.get_or_create(event_id=event_id)
    lock.lock(request.user, request.data.get("reason", ""))
    _log_action(request, "event_manpower_locked", lock, event_id=event_id, details={"reason": lock.reason})
    return Response(EventManpowerLockSerializer(lock).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unlock_event_manpower(request, event_id):
    denied = _require_role(request, ADMIN_ROLES)
    if denied:
        return denied

    lock, _ = EventManpowerLock.objects.get_or_create(event_id=event_id)
    lock.unlock(request.user)
    _log_action(request, "event_manpower_unlocked", lock, event_id=event_id)
    return Response(EventManpowerLockSerializer(lock).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def event_lock_status(request, event_id):
    lock, _ = EventManpowerLock.objects.get_or_create(event_id=event_id)
    return Response(EventManpowerLockSerializer(lock).data)


class InvoiceWorkflowList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return InvoiceWorkflow.objects.select_related("event", "event_department__department", "freelancer", "adjustment")

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request):
        denied = _require_accounts_access(request)
        if denied:
            return denied
        qs = _filter_to_accounts_scope(request, self.get_queryset(), "event_id")
        if request.query_params.get("event"):
            qs = qs.filter(event_id=request.query_params["event"])
        if request.query_params.get("department"):
            qs = qs.filter(event_department__department_id=request.query_params["department"])
        if request.query_params.get("freelancer"):
            qs = qs.filter(freelancer_id=request.query_params["freelancer"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(InvoiceWorkflowSerializer(qs, many=True).data)

    def post(self, request):
        adjustment = get_object_or_404(PostEventAdjustment, pk=request.data.get("adjustment"))
        denied = _require_manpower_event_access(request, adjustment.allocation.event_department.event_id)
        if denied:
            return denied
        if adjustment.admin_approval_status != "approved":
            return Response(
                {"detail": "Invoice can only be created from approved adjustments."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = InvoiceWorkflow.objects.filter(adjustment=adjustment).first()
        if existing:
            return Response(InvoiceWorkflowSerializer(existing).data, status=status.HTTP_200_OK)

        invoice_number = request.data.get("invoice_number") or f"INV-{timezone.now().strftime('%Y%m%d')}-{str(adjustment.id)[:8].upper()}"
        payload = dict(request.data)
        payload.update(
            {
                "event": adjustment.allocation.event_department.event_id,
                "event_department": adjustment.allocation.event_department_id,
                "freelancer": adjustment.allocation.freelancer_id,
                "payable_amount": adjustment.revised_total,
                "invoice_number": invoice_number,
                "status": "draft",
            }
        )
        ser = InvoiceWorkflowSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        obj = ser.save(adjustment=adjustment)
        _log_action(request, "invoice_created", obj, event_id=obj.event_id, details={"status": obj.status})
        return Response(InvoiceWorkflowSerializer(obj).data, status=status.HTTP_201_CREATED)


class InvoiceWorkflowDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_base_queryset(self):
        return InvoiceWorkflow.objects.select_related("event", "event_department__department", "freelancer", "adjustment")

    def get_queryset(self):
        return self.get_base_queryset()

    def get(self, request, pk):
        denied = _require_accounts_access(request)
        if denied:
            return denied
        obj = get_object_or_404(_filter_to_accounts_scope(request, self.get_queryset(), "event_id"), pk=pk)
        return Response(InvoiceWorkflowSerializer(obj).data)

    def put(self, request, pk):
        denied = _require_accounts_access(request)
        if denied:
            return denied
        obj = get_object_or_404(_filter_to_accounts_scope(request, self.get_queryset(), "event_id"), pk=pk)
        ser = InvoiceWorkflowSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        updated = ser.save()
        _log_action(request, "invoice_updated", updated, event_id=updated.event_id)
        return Response(InvoiceWorkflowSerializer(updated).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def invoice_transition(request, pk):
    denied = _require_accounts_access(request)
    if denied:
        return denied
    obj = get_object_or_404(InvoiceWorkflow, pk=pk)
    allowed_event_ids = _get_accounts_event_ids_for_user(request.user)
    if allowed_event_ids is not None and obj.event_id not in allowed_event_ids:
        return Response(
            {"detail": "Accounts department assignment required for this event."},
            status=status.HTTP_403_FORBIDDEN,
        )
    new_status = request.data.get("status")
    if new_status not in dict(InvoiceWorkflow.STATUS_CHOICES):
        return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        obj.transition_to(new_status)
    except ValueError as err:
        return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)
    if new_status == "paid" and request.data.get("paid_reference"):
        obj.paid_reference = request.data["paid_reference"]
    obj.save()
    _log_action(request, "invoice_transitioned", obj, event_id=obj.event_id, details={"status": obj.status})
    return Response(InvoiceWorkflowSerializer(obj).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue_adjustment_secure_link(request, allocation_id):
    allocation = get_object_or_404(FreelancerAllocation, pk=allocation_id)
    denied = _require_manpower_event_access(request, allocation.event_department.event_id)
    if denied:
        return denied
    adjustment, created = PostEventAdjustment.objects.get_or_create(allocation=allocation)
    # If not submitted, sync data to ensure it matches current MoU commercials
    if not adjustment.freelancer_submitted_at:
        cost = allocation.cost_sheet
        adjustment.actual_days_worked = cost.days_planned
        adjustment.total_engagement_days = cost.days_planned
        
        # Initial period from allocation dates
        if allocation.start_date and allocation.end_date:
            adjustment.engagement_periods = [{
                "start": str(allocation.start_date),
                "end": str(allocation.end_date),
                "days": float(cost.days_planned)
            }]
        
        adjustment.override_negotiated_rate = cost.negotiated_rate
        if not adjustment.secure_token:
            adjustment.secure_token = uuid.uuid4()
        adjustment.save()
        _create_revision(adjustment, "prefill", user=request.user)
    elif not adjustment.secure_token:
        adjustment.secure_token = uuid.uuid4()
        adjustment.save(update_fields=["secure_token"])
    return Response(
        {
            "adjustment_id": adjustment.id,
            "secure_token": adjustment.secure_token,
            "secure_link": f"/adjustment/{adjustment.secure_token}",
        }
    )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def public_adjustment_interaction(request, token):
    try:
        adjustment = PostEventAdjustment.objects.select_related(
            "allocation__freelancer",
            "allocation__event_department__event",
            "allocation__cost_sheet",
            "allocation__requirement",
        ).prefetch_related(
            "allocation__daily_meals",
            "allocation__requirement__sessions"
        ).get(secure_token=token)
    except (PostEventAdjustment.DoesNotExist, ValueError):
        return Response({"error": "Invalid token"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        from .serializers import AllocationDailyMealSerializer
        from Events.serializers.session_serializers import SessionSerializer
        
        # Get sessions from requirement
        sessions_data = []
        if adjustment.allocation.requirement:
            sessions_data = SessionSerializer(adjustment.allocation.requirement.sessions.all(), many=True).data

        return Response(
            {
                "id": adjustment.id,
                "event_name": adjustment.allocation.event_department.event.name,
                "freelancer_name": adjustment.allocation.freelancer.name,
                "is_editable": adjustment.allocation.is_adjustment_editable,
                "planned_days": adjustment.allocation.cost_sheet.days_planned,
                "planned_rate": adjustment.allocation.cost_sheet.negotiated_rate,
                "travel_costs": adjustment.allocation.cost_sheet.travel_costs,
                "actual_days_worked": adjustment.actual_days_worked,
                "total_engagement_days": adjustment.total_engagement_days,
                "engagement_periods": adjustment.engagement_periods,
                "travel_adjustments": adjustment.travel_adjustments,
                "other_adjustments": adjustment.other_adjustments,
                "override_negotiated_rate": adjustment.override_negotiated_rate,
                "freelancer_comments": adjustment.freelancer_comments,
                "freelancer_submitted_at": adjustment.freelancer_submitted_at,
                "status": adjustment.admin_approval_status,
                "total_meal_allowance": adjustment.allocation.total_meal_allowance,
                "daily_meals": AllocationDailyMealSerializer(adjustment.allocation.daily_meals.all(), many=True).data,
                "sessions": sessions_data,
            }
        )

    if adjustment.freelancer_submitted_at:
        return Response(
            {"error": "Adjustment has already been submitted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_fields = {
        "actual_days_worked",
        "total_engagement_days",
        "engagement_periods",
        "travel_adjustments",
        "other_adjustments",
        "override_negotiated_rate",
        "freelancer_comments",
    }

    updates = {k: v for k, v in request.data.items() if k in allowed_fields}
    ser = PostEventAdjustmentSerializer(adjustment, data=updates, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save(freelancer_submitted_at=timezone.now())
    _create_revision(adjustment, "submission")
    return Response({"status": "submitted", "adjustment_id": adjustment.id})


class ManpowerAuditLogList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_role(request, ADMIN_ROLES)
        if denied:
            return denied
        qs = ManpowerAuditLog.objects.select_related("actor", "event")
        if request.query_params.get("event"):
            qs = qs.filter(event_id=request.query_params["event"])
        return Response(ManpowerAuditLogSerializer(qs[:500], many=True).data)


@document_api_view(
    {
        "get": doc_retrieve(
            response=ManpowerSettingsSerializer,
            description="Retrieve global manpower settings (default meal rates)",
            tags=["Manpower: Settings"],
        ),
        "put": doc_update(
            request=ManpowerSettingsSerializer,
            response=ManpowerSettingsSerializer,
            description="Update global manpower settings (default meal rates)",
            tags=["Manpower: Settings"],
        ),
    }
)
class ManpowerSettingsDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            denied = _require_role(request, ADMIN_ROLES)
            if denied:
                return denied
            obj = ManpowerSettings.get_settings()
            return Response(ManpowerSettingsSerializer(obj).data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error fetching manpower settings", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request):
        try:
            denied = _require_role(request, ADMIN_ROLES)
            if denied:
                return denied
            obj = ManpowerSettings.get_settings()
            ser = ManpowerSettingsSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            _log_action(request, "manpower_settings_updated", obj, details={
                "default_breakfast_rate": str(obj.default_breakfast_rate),
                "default_lunch_rate": str(obj.default_lunch_rate),
                "default_dinner_rate": str(obj.default_dinner_rate),
            })
            return Response(ser.data)
        except Http404:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": "Error updating manpower settings", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

