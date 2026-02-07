from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.db import transaction
from Events.models.event_model import Event
from Departments.mixins import DepartmentAccessMixin
from Departments.permissions import PermissionChecker
from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    BudgetLineItem,
    BudgetFieldPermission,
    ModelPermission,
    DepartmentModelAccess,
    User,
)
from Departments.serializers import (
    DepartmentSerializer,
    EventDepartmentSerializer,
    EventDepartmentStaffAssignmentSerializer,
    BudgetLineItemSerializer,
    BudgetFieldPermissionSerializer,
    UserEventDepartmentFieldAccessSerializer,
    ModelPermissionSerializer,
    DepartmentModelAccessSerializer,
)
from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)
from Departments.serializers import BUDGET_FIELD_KEYS

# ─────────────────────────────────────────────────────────────
# Department (global master)
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=DepartmentSerializer(many=True),
            parameters=[
                query_param("name", "str", False, "Filter by name (icontains)"),
                query_param("slug", "str", False, "Filter by slug (exact)"),
            ],
            description="List all departments (global master)",
            tags=["Departments"],
        ),
        "post": doc_create(
            request=DepartmentSerializer,
            response=DepartmentSerializer,
            description="Create a department (global)",
            tags=["Departments"],
        ),
    }
)
class DepartmentList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Department.objects.all()
            name = request.query_params.get("name")
            slug = request.query_params.get("slug")
            if name:
                qs = qs.filter(name__icontains=name)
            if slug:
                qs = qs.filter(slug=slug)
            return Response(DepartmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching departments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = DepartmentSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=DepartmentSerializer,
            description="Retrieve a department",
            tags=["Departments"],
        ),
        "put": doc_update(
            request=DepartmentSerializer,
            response=DepartmentSerializer,
            description="Update a department",
            tags=["Departments"],
        ),
        "delete": doc_destroy(description="Delete a department", tags=["Departments"]),
    }
)
class DepartmentDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(Department, pk=pk)
            return Response(DepartmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(Department, pk=pk)
            ser = DepartmentSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(DepartmentSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(Department, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────
# EventDepartment (Event × Department)
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=EventDepartmentSerializer(many=True),
            parameters=[
                query_param("event", "uuid", False, "Filter by event ID"),
                query_param("department", "uuid", False, "Filter by department ID"),
            ],
            description="List all event-departments",
            tags=["Event Departments"],
        ),
        "post": doc_create(
            request=EventDepartmentSerializer,
            response=EventDepartmentSerializer,
            description="Create an event-department link",
            tags=["Event Departments"],
        ),
    }
)
class EventDepartmentList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = EventDepartment.objects.select_related("event", "department").all()
            event_id = request.query_params.get("event")
            dept_id = request.query_params.get("department")
            if event_id:
                qs = qs.filter(event_id=event_id)
            if dept_id:
                qs = qs.filter(department_id=dept_id)
            return Response(EventDepartmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event-departments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventDepartmentSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating event-department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventDepartmentSerializer,
            description="Retrieve an event-department link",
            tags=["Event Departments"],
        ),
        "put": doc_update(
            request=EventDepartmentSerializer,
            response=EventDepartmentSerializer,
            description="Update an event-department link",
            tags=["Event Departments"],
        ),
        "delete": doc_destroy(
            description="Delete an event-department link",
            tags=["Event Departments"],
        ),
    }
)
class EventDepartmentDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartment, pk=pk)
            return Response(EventDepartmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching event-department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartment, pk=pk)
            ser = EventDepartmentSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(EventDepartmentSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating event-department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartment, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting event-department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventDepartmentSerializer(many=True),
            description="List all event-departments under a specific event",
            tags=["Event Departments"],
        )
    }
)
class EventDepartmentsByEventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            get_object_or_404(Event, pk=pk)
            qs = EventDepartment.objects.filter(event_id=pk).select_related(
                "event", "department"
            )
            return Response(EventDepartmentSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing event-departments for event",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────
# EventDepartment Staff Assignments
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=EventDepartmentStaffAssignmentSerializer(many=True),
            parameters=[
                query_param(
                    "event_department", "uuid", False, "Filter by event-department ID"
                ),
                query_param("user", "uuid", False, "Filter by user ID"),
            ],
            description="List event-department staff assignments",
            tags=["EventDepartment Staff"],
        ),
        "post": doc_create(
            request=EventDepartmentStaffAssignmentSerializer,
            response=EventDepartmentStaffAssignmentSerializer,
            description="Create an event-department staff assignment",
            tags=["EventDepartment Staff"],
        ),
    }
)
class EventDepartmentStaffAssignmentList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = EventDepartmentStaffAssignment.objects.select_related(
                "event_department", "user"
            ).all()
            ed = request.query_params.get("event_department")
            user = request.query_params.get("user")
            if ed:
                qs = qs.filter(event_department_id=ed)
            if user:
                qs = qs.filter(user_id=user)
            return Response(
                EventDepartmentStaffAssignmentSerializer(qs, many=True).data
            )
        except Exception as e:
            return Response(
                {"detail": "Error fetching staff assignments", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = EventDepartmentStaffAssignmentSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating staff assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=EventDepartmentStaffAssignmentSerializer,
            description="Retrieve an event-department staff assignment",
            tags=["EventDepartment Staff"],
        ),
        "put": doc_update(
            request=EventDepartmentStaffAssignmentSerializer,
            response=EventDepartmentStaffAssignmentSerializer,
            description="Update an event-department staff assignment",
            tags=["EventDepartment Staff"],
        ),
        "delete": doc_destroy(
            description="Delete an event-department staff assignment",
            tags=["EventDepartment Staff"],
        ),
    }
)
class EventDepartmentStaffAssignmentDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartmentStaffAssignment, pk=pk)
            return Response(EventDepartmentStaffAssignmentSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching staff assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartmentStaffAssignment, pk=pk)
            ser = EventDepartmentStaffAssignmentSerializer(
                obj, data=request.data, partial=True
            )
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(EventDepartmentStaffAssignmentSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating staff assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(EventDepartmentStaffAssignment, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting staff assignment", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=EventDepartmentStaffAssignmentSerializer(many=True),
            description="List staff assignments for one event-department",
            tags=["EventDepartment Staff"],
        )
    }
)
class StaffAssignmentsByEventDepartmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            get_object_or_404(EventDepartment, pk=pk)
            qs = EventDepartmentStaffAssignment.objects.filter(
                event_department_id=pk
            ).select_related("event_department", "user")
            return Response(
                EventDepartmentStaffAssignmentSerializer(qs, many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing staff assignments for event-department",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────
# Budget Line Items
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=BudgetLineItemSerializer(many=True),
            parameters=[
                query_param(
                    "event_department", "uuid", False, "Filter by event-department ID"
                ),
                query_param("category", "str", False, "Filter by category (icontains)"),
                query_param("payment_status", "str", False, "Filter by payment status"),
            ],
            description="List budget line items",
            tags=["Budget Items"],
        ),
        "post": doc_create(
            request=BudgetLineItemSerializer,
            response=BudgetLineItemSerializer,
            description="Create a budget line item",
            tags=["Budget Items"],
        ),
    }
)
class BudgetLineItemList(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return BudgetLineItem.objects.select_related("event_department").all()

    def get(self, request):
        try:
            qs = self.get_queryset()
            ed = request.query_params.get("event_department")
            cat = request.query_params.get("category")
            pstat = request.query_params.get("payment_status")
            if ed:
                qs = qs.filter(event_department_id=ed)
            if cat:
                qs = qs.filter(category__icontains=cat)
            if pstat:
                qs = qs.filter(payment_status=pstat)
            return Response(BudgetLineItemSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching budget items", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            # Check if user has access to the event_department's event
            event_dept_id = request.data.get('event_department')
            if event_dept_id:
                try:
                    event_dept = EventDepartment.objects.get(id=event_dept_id)
                    accessible_events = PermissionChecker.get_user_accessible_events(request.user)
                    if not accessible_events.filter(id=event_dept.event_id).exists() and request.user.role != 'super_admin':
                        return Response(
                            {"detail": "You don't have access to this event"},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except EventDepartment.DoesNotExist:
                    pass
            ser = BudgetLineItemSerializer(data=request.data, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating budget item", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=BudgetLineItemSerializer,
            description="Retrieve a budget line item",
            tags=["Budget Items"],
        ),
        "put": doc_update(
            request=BudgetLineItemSerializer,
            response=BudgetLineItemSerializer,
            description="Update a budget line item",
            tags=["Budget Items"],
        ),
        "delete": doc_destroy(
            description="Delete a budget line item", tags=["Budget Items"]
        ),
    }
)
class BudgetLineItemDetail(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return BudgetLineItem.objects.select_related("event_department").all()

    def get(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            return Response(BudgetLineItemSerializer(obj, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching budget item", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            qs = self.get_queryset()
            obj = get_object_or_404(qs, pk=pk)
            ser = BudgetLineItemSerializer(obj, data=request.data, partial=True, context=self.get_serializer_context())
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(BudgetLineItemSerializer(obj, context=self.get_serializer_context()).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating budget item", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(BudgetLineItem, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting budget item", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=BudgetLineItemSerializer(many=True),
            description="List budget items for one event-department",
            tags=["Budget Items"],
        )
    }
)
class BudgetItemsByEventDepartmentAPIView(DepartmentAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Override to provide base queryset for filtering."""
        return BudgetLineItem.objects.select_related("event_department").all()

    def get(self, request, pk):
        try:
            # Ensure user has access to this event-department's event
            event_dept = get_object_or_404(EventDepartment, pk=pk)
            accessible_events = PermissionChecker.get_user_accessible_events(request.user)
            if not accessible_events.filter(id=event_dept.event_id).exists() and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have access to this event"},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = self.get_queryset().filter(event_department_id=pk)
            return Response(BudgetLineItemSerializer(qs, many=True, context=self.get_serializer_context()).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing budget items for event-department",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────
# Budget Field Permissions
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=BudgetFieldPermissionSerializer(many=True),
            parameters=[
                query_param(
                    "event_department", "uuid", False, "Filter by event-department ID"
                ),
                query_param("user", "uuid", False, "Filter by user ID"),
                query_param("field_key", "str", False, "Filter by field key"),
            ],
            description="List budget field permissions",
            tags=["Budget Field Permissions"],
        ),
        "post": doc_create(
            request=BudgetFieldPermissionSerializer,
            response=BudgetFieldPermissionSerializer,
            description="Create a budget field permission",
            tags=["Budget Field Permissions"],
        ),
    }
)
class BudgetFieldPermissionList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = BudgetFieldPermission.objects.select_related(
                "event_department", "user"
            ).all()
            ed = request.query_params.get("event_department")
            user = request.query_params.get("user")
            field_key = request.query_params.get("field_key")
            if ed:
                qs = qs.filter(event_department_id=ed)
            if user:
                qs = qs.filter(user_id=user)
            if field_key:
                qs = qs.filter(field_key=field_key)
            return Response(BudgetFieldPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = BudgetFieldPermissionSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=BudgetFieldPermissionSerializer,
            description="Retrieve a budget field permission",
            tags=["Budget Field Permissions"],
        ),
        "put": doc_update(
            request=BudgetFieldPermissionSerializer,
            response=BudgetFieldPermissionSerializer,
            description="Update a budget field permission",
            tags=["Budget Field Permissions"],
        ),
        "delete": doc_destroy(
            description="Delete a budget field permission",
            tags=["Budget Field Permissions"],
        ),
    }
)
class BudgetFieldPermissionDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(BudgetFieldPermission, pk=pk)
            return Response(BudgetFieldPermissionSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            obj = get_object_or_404(BudgetFieldPermission, pk=pk)
            ser = BudgetFieldPermissionSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(BudgetFieldPermissionSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(BudgetFieldPermission, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting field permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=BudgetFieldPermissionSerializer(many=True),
            description="List all field permissions for one event-department",
            tags=["Budget Field Permissions"],
        )
    }
)
class FieldPermsByEventDepartmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            get_object_or_404(EventDepartment, pk=pk)
            qs = BudgetFieldPermission.objects.filter(
                event_department_id=pk
            ).select_related("event_department", "user")
            return Response(BudgetFieldPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error listing field permissions for event-department",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------------
# Get a user's allowed fields on one EventDepartment
# GET /event-departments/{event_dept_id}/users/{user_id}/field-perms/
# ----------------------------------------------------------------------------
@document_api_view(
    {
        "get": doc_list(
            response=BudgetFieldPermissionSerializer(many=True),
            description="List all field permissions (objects) for a user on one event-department",
            tags=["Budget Field Permissions"],
        )
    }
)
class EventDepartmentUserFieldPermsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_dept_pk, user_pk):
        try:
            get_object_or_404(EventDepartment, pk=event_dept_pk)
            get_object_or_404(User, pk=user_pk)

            qs = BudgetFieldPermission.objects.filter(
                event_department_id=event_dept_pk, user_id=user_pk
            )

            # If you want ONLY the keys (fast path):
            only_keys = request.query_params.get("only_keys")
            if only_keys in ("1", "true", "True"):
                keys = list(qs.values_list("field_key", flat=True))
                return Response({"field_keys": keys})

            # Otherwise return full objects:
            return Response(BudgetFieldPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching user field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------------
# Bulk SET (replace) a user's allowed fields on one EventDepartment
# POST /event-departments/{event_dept_id}/users/{user_id}/field-perms/set/
# Body: { "field_keys": ["category","unit_rate", ...] }
# ----------------------------------------------------------------------------
@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk SET (replace) a user's allowed fields for an event-department",
            tags=["Budget Field Permissions"],
        )
    }
)
class EventDepartmentUserFieldPermsSetAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_dept_pk, user_pk):
        try:
            ed = get_object_or_404(EventDepartment, pk=event_dept_pk)
            user = get_object_or_404(User, pk=user_pk)

            field_keys = request.data.get("field_keys", [])
            if not isinstance(field_keys, list):
                return Response(
                    {"detail": "field_keys must be a list of strings."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate keys
            invalid = [k for k in field_keys if k not in BUDGET_FIELD_KEYS]
            if invalid:
                return Response(
                    {"detail": f"Invalid field_key(s): {invalid}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                # Compute desired set vs current set
                current = set(
                    BudgetFieldPermission.objects.filter(
                        event_department=ed, user=user
                    ).values_list("field_key", flat=True)
                )
                desired = set(field_keys)

                # Create missing
                to_create = desired - current
                BudgetFieldPermission.objects.bulk_create(
                    [
                        BudgetFieldPermission(
                            event_department=ed, user=user, field_key=k
                        )
                        for k in to_create
                    ],
                    ignore_conflicts=True,  # in case of race
                )

                # Delete extras
                to_delete = current - desired
                if to_delete:
                    BudgetFieldPermission.objects.filter(
                        event_department=ed, user=user, field_key__in=to_delete
                    ).delete()

            # Return final state
            final_keys = list(
                BudgetFieldPermission.objects.filter(
                    event_department=ed, user=user
                ).values_list("field_key", flat=True)
            )
            return Response({"field_keys": final_keys}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": "Error setting field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------------
# Bulk ADD: add some fields to user's allowed fields (no replace)
# POST /event-departments/{event_dept_id}/users/{user_id}/field-perms/add/
# Body: { "field_keys": ["...", "..."] }
# ----------------------------------------------------------------------------
@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk ADD specific fields to a user's allowed fields (no replace)",
            tags=["Budget Field Permissions"],
        )
    }
)
class EventDepartmentUserFieldPermsAddAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_dept_pk, user_pk):
        try:
            ed = get_object_or_404(EventDepartment, pk=event_dept_pk)
            user = get_object_or_404(User, pk=user_pk)

            field_keys = request.data.get("field_keys", [])
            if not isinstance(field_keys, list):
                return Response(
                    {"detail": "field_keys must be a list of strings."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invalid = [k for k in field_keys if k not in BUDGET_FIELD_KEYS]
            if invalid:
                return Response(
                    {"detail": f"Invalid field_key(s): {invalid}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                existing = set(
                    BudgetFieldPermission.objects.filter(
                        event_department=ed, user=user
                    ).values_list("field_key", flat=True)
                )
                to_create = [k for k in field_keys if k not in existing]

                BudgetFieldPermission.objects.bulk_create(
                    [
                        BudgetFieldPermission(
                            event_department=ed, user=user, field_key=k
                        )
                        for k in to_create
                    ],
                    ignore_conflicts=True,
                )

            final_keys = list(
                BudgetFieldPermission.objects.filter(
                    event_department=ed, user=user
                ).values_list("field_key", flat=True)
            )
            return Response({"field_keys": final_keys}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": "Error adding field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------------
# Bulk REMOVE: remove some fields from user's allowed fields (no replace)
# POST /event-departments/{event_dept_id}/users/{user_id}/field-perms/remove/
# Body: { "field_keys": ["...", "..."] }
# ----------------------------------------------------------------------------
@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk REMOVE specific fields from a user's allowed fields (no replace)",
            tags=["Budget Field Permissions"],
        )
    }
)
class EventDepartmentUserFieldPermsRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_dept_pk, user_pk):
        try:
            ed = get_object_or_404(EventDepartment, pk=event_dept_pk)
            user = get_object_or_404(User, pk=user_pk)

            field_keys = request.data.get("field_keys", [])
            if not isinstance(field_keys, list):
                return Response(
                    {"detail": "field_keys must be a list of strings."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invalid = [k for k in field_keys if k not in BUDGET_FIELD_KEYS]
            if invalid:
                return Response(
                    {"detail": f"Invalid field_key(s): {invalid}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                if field_keys:
                    BudgetFieldPermission.objects.filter(
                        event_department=ed, user=user, field_key__in=field_keys
                    ).delete()

            final_keys = list(
                BudgetFieldPermission.objects.filter(
                    event_department=ed, user=user
                ).values_list("field_key", flat=True)
            )
            return Response({"field_keys": final_keys}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": "Error removing field permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _build_access_rows(assignments, user_id):
    """
    Utility to build the response rows with one DB round-trip
    for the permissions, avoiding N+1.
    """
    if not assignments:
        return []

    ed_ids = [a.event_department_id for a in assignments]

    perms_map = {}
    for ed_id, field_key in BudgetFieldPermission.objects.filter(
        user_id=user_id, event_department_id__in=ed_ids
    ).values_list("event_department_id", "field_key"):
        perms_map.setdefault(str(ed_id), []).append(field_key)

    data = []
    for a in assignments:
        ed = a.event_department
        data.append(
            {
                "event_department": {
                    "id": ed.id,
                    "event": {"id": ed.event.id, "name": ed.event.name},
                    "department": {"id": ed.department.id, "name": ed.department.name},
                },
                "role": a.role,
                "field_keys": perms_map.get(str(ed.id), []),
            }
        )
    return data


@document_api_view(
    {
        "get": doc_list(
            response=UserEventDepartmentFieldAccessSerializer(many=True),
            description="All event-departments (for a single event) the user is assigned to, with allowed budget field keys.",
            tags=["Event-Department: User Field Access"],
        )
    }
)
class UserEventScopedDepartmentFieldAccessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    GET /api/users/<user_pk>/events/<event_pk>/departments/field-access/
    → Only event-departments under <event_pk> where the user is assigned + allowed field_keys.
    """

    def get(self, request, user_pk, event_pk):
        try:
            user = get_object_or_404(User, pk=user_pk)
            get_object_or_404(Event, pk=event_pk)

            assignments = list(
                EventDepartmentStaffAssignment.objects.select_related(
                    "event_department__event",
                    "event_department__department",
                ).filter(
                    user_id=user.id,
                    event_department__event_id=event_pk,
                )
            )
            rows = _build_access_rows(assignments, user.id)
            serializer = UserEventDepartmentFieldAccessSerializer(rows, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {
                    "detail": "Error fetching user field access for event",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
