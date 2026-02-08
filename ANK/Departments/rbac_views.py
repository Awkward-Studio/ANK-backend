from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.contrib.contenttypes.models import ContentType
from Departments.models import (
    Department,
    EventDepartment,
    ModelPermission,
    DepartmentModelAccess,
    User,
)
from Departments.serializers import (
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


# ─────────────────────────────────────────────────────────────
# RBAC Permission Management
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "get": doc_list(
            response=ModelPermissionSerializer(many=True),
            parameters=[
                query_param("user", "uuid", False, "Filter by user ID"),
                query_param("event_department", "uuid", False, "Filter by event-department ID"),
                query_param("content_type", "int", False, "Filter by ContentType ID"),
                query_param("model", "str", False, "Filter by model name (e.g., 'guest', 'event')"),
                query_param("field_name", "str", False, "Filter by field name"),
            ],
            description="List all model permissions (field-level permissions)",
            tags=["RBAC: Model Permissions"],
        ),
        "post": doc_create(
            request=ModelPermissionSerializer,
            response=ModelPermissionSerializer,
            description="Create a model permission (field-level permission)",
            tags=["RBAC: Model Permissions"],
        ),
    }
)
class ModelPermissionList(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin and department_head can manage permissions."""
        if request.user.role not in ['super_admin', 'department_head']:
            raise PermissionDenied("Only super admins and department heads can manage permissions.")

    def get(self, request):
        self.check_permissions(request)
        try:
            qs = ModelPermission.objects.select_related(
                'user', 'event_department', 'content_type'
            ).all()
            
            user_id = request.query_params.get("user")
            event_dept_id = request.query_params.get("event_department")
            content_type_id = request.query_params.get("content_type")
            model_name = request.query_params.get("model")
            field_name = request.query_params.get("field_name")
            
            if user_id:
                qs = qs.filter(user_id=user_id)
            if event_dept_id:
                qs = qs.filter(event_department_id=event_dept_id)
            if content_type_id:
                qs = qs.filter(content_type_id=content_type_id)
            if model_name:
                from django.contrib.contenttypes.models import ContentType
                qs = qs.filter(content_type__model=model_name)
            if field_name:
                qs = qs.filter(field_name=field_name)
            
            return Response(ModelPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching model permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        self.check_permissions(request)
        try:
            ser = ModelPermissionSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating model permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=ModelPermissionSerializer,
            description="Retrieve a model permission",
            tags=["RBAC: Model Permissions"],
        ),
        "put": doc_update(
            request=ModelPermissionSerializer,
            response=ModelPermissionSerializer,
            description="Update a model permission",
            tags=["RBAC: Model Permissions"],
        ),
        "delete": doc_destroy(
            description="Delete a model permission",
            tags=["RBAC: Model Permissions"],
        ),
    }
)
class ModelPermissionDetail(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin and department_head can manage permissions."""
        if request.user.role not in ['super_admin', 'department_head']:
            raise PermissionDenied("Only super admins and department heads can manage permissions.")

    def get(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(ModelPermission, pk=pk)
            return Response(ModelPermissionSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching model permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(ModelPermission, pk=pk)
            ser = ModelPermissionSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ModelPermissionSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating model permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(ModelPermission, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting model permission", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=ModelPermissionSerializer(many=True),
            description="List all model permissions for a specific event-department",
            tags=["RBAC: Model Permissions"],
        )
    }
)
class ModelPermissionsByEventDepartmentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin and department_head can view permissions."""
        if request.user.role not in ['super_admin', 'department_head']:
            raise PermissionDenied("Only super admins and department heads can view permissions.")

    def get(self, request, pk):
        self.check_permissions(request)
        try:
            get_object_or_404(EventDepartment, pk=pk)
            qs = ModelPermission.objects.filter(
                event_department_id=pk
            ).select_related('user', 'event_department', 'content_type')
            return Response(ModelPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing model permissions for event-department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=ModelPermissionSerializer(many=True),
            description="List all model permissions for a specific user",
            tags=["RBAC: Model Permissions"],
        )
    }
)
class ModelPermissionsByUserAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Users can view their own permissions, super_admin and department_head can view any."""
        user_pk = request.resolver_match.kwargs.get('pk')
        if request.user.role not in ['super_admin', 'department_head'] and str(request.user.id) != str(user_pk):
            raise PermissionDenied("You can only view your own permissions.")

    def get(self, request, pk):
        self.check_permissions(request)
        try:
            get_object_or_404(User, pk=pk)
            qs = ModelPermission.objects.filter(
                user_id=pk
            ).select_related('user', 'event_department', 'content_type')
            return Response(ModelPermissionSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing model permissions for user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=DepartmentModelAccessSerializer(many=True),
            parameters=[
                query_param("department", "uuid", False, "Filter by department ID"),
                query_param("content_type", "int", False, "Filter by ContentType ID"),
                query_param("model", "str", False, "Filter by model name"),
            ],
            description="List all department-model access mappings",
            tags=["RBAC: Department Model Access"],
        ),
        "post": doc_create(
            request=DepartmentModelAccessSerializer,
            response=DepartmentModelAccessSerializer,
            description="Create a department-model access mapping",
            tags=["RBAC: Department Model Access"],
        ),
    }
)
class DepartmentModelAccessList(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin can manage department-model access."""
        if request.user.role != 'super_admin':
            raise PermissionDenied("Only super admins can manage department-model access.")

    def get(self, request):
        self.check_permissions(request)
        try:
            qs = DepartmentModelAccess.objects.select_related(
                'department', 'content_type'
            ).all()
            
            dept_id = request.query_params.get("department")
            content_type_id = request.query_params.get("content_type")
            model_name = request.query_params.get("model")
            
            if dept_id:
                qs = qs.filter(department_id=dept_id)
            if content_type_id:
                qs = qs.filter(content_type_id=content_type_id)
            if model_name:
                qs = qs.filter(content_type__model=model_name)
            
            return Response(DepartmentModelAccessSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        self.check_permissions(request)
        try:
            ser = DepartmentModelAccessSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=DepartmentModelAccessSerializer,
            description="Retrieve a department-model access mapping",
            tags=["RBAC: Department Model Access"],
        ),
        "put": doc_update(
            request=DepartmentModelAccessSerializer,
            response=DepartmentModelAccessSerializer,
            description="Update a department-model access mapping",
            tags=["RBAC: Department Model Access"],
        ),
        "delete": doc_destroy(
            description="Delete a department-model access mapping",
            tags=["RBAC: Department Model Access"],
        ),
    }
)
class DepartmentModelAccessDetail(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin can manage department-model access."""
        if request.user.role != 'super_admin':
            raise PermissionDenied("Only super admins can manage department-model access.")

    def get(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(DepartmentModelAccess, pk=pk)
            return Response(DepartmentModelAccessSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(DepartmentModelAccess, pk=pk)
            ser = DepartmentModelAccessSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(DepartmentModelAccessSerializer(obj).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        self.check_permissions(request)
        try:
            obj = get_object_or_404(DepartmentModelAccess, pk=pk)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=DepartmentModelAccessSerializer(many=True),
            description="List all model access mappings for a specific department",
            tags=["RBAC: Department Model Access"],
        )
    }
)
class DepartmentModelAccessByDepartmentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin can view department-model access."""
        if request.user.role != 'super_admin':
            raise PermissionDenied("Only super admins can view department-model access.")

    def get(self, request, pk):
        self.check_permissions(request)
        try:
            get_object_or_404(Department, pk=pk)
            qs = DepartmentModelAccess.objects.filter(
                department_id=pk
            ).select_related('department', 'content_type')
            return Response(DepartmentModelAccessSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing department-model access for department", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────
# Available Models for RBAC
# ─────────────────────────────────────────────────────────────


# Models that can be assigned to departments
RBAC_AVAILABLE_MODELS = [
    ('Events', 'event', 'Event'),
    ('Guest', 'guest', 'Guest'),
    ('Events', 'session', 'Session'),
    ('Events', 'eventregistration', 'Event Registration'),
    ('Logistics', 'traveldetail', 'Travel Detail'),
    ('Logistics', 'accommodation', 'Accommodation'),
    ('Departments', 'budgetlineitem', 'Budget Line Item'),
    ('Events', 'extraattendee', 'Extra Attendee'),
]


@document_api_view(
    {
        "get": doc_list(
            description="List all available models for RBAC (for department-model access and field permissions)",
            tags=["RBAC: Helper Endpoints"],
        ),
    }
)
class AvailableModelsAPIView(APIView):
    """
    GET /api/rbac/available-models/
    
    Returns a list of all models that can be assigned to departments or used for field permissions.
    This endpoint helps the frontend display a dropdown/list of available models.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            models = []
            for app_label, model_name, display_name in RBAC_AVAILABLE_MODELS:
                try:
                    content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                    models.append({
                        "model": model_name,
                        "display_name": display_name,
                        "content_type_id": content_type.id,
                        "app_label": content_type.app_label,
                    })
                except ContentType.DoesNotExist:
                    # Skip if ContentType doesn't exist (model not installed)
                    continue
            
            return Response({
                "models": models,
                "count": len(models)
            })
        except Exception as e:
            return Response(
                {"detail": "Error fetching available models", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            description="Get field names for a specific model (for field permission assignment)",
            tags=["RBAC: Helper Endpoints"],
        ),
    }
)
class ModelFieldsAPIView(APIView):
    """
    GET /api/rbac/models/<model_name>/fields/
    
    Returns a list of all field names for a specific model.
    This endpoint helps the frontend display available fields when assigning field permissions.
    
    Example: GET /api/rbac/models/guest/fields/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, model_name):
        try:
            # Get ContentType for the model
            try:
                content_type = ContentType.objects.get(model=model_name)
            except ContentType.DoesNotExist:
                return Response(
                    {"detail": f"Model '{model_name}' not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Get model class
            model_class = content_type.model_class()
            if not model_class:
                return Response(
                    {"detail": f"Model class for '{model_name}' not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Get field names using the same function as ModelPermission validation
            from Departments.models import get_model_fields
            fields = get_model_fields(model_class)
            
            return Response({
                "model": model_name,
                "content_type_id": content_type.id,
                "fields": sorted(fields),
                "count": len(fields)
            })
        except Exception as e:
            return Response(
                {"detail": "Error fetching model fields", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            description="Get RBAC choices and metadata (roles, permission types, etc.)",
            tags=["RBAC: Helper Endpoints"],
        ),
    }
)
class RBACMetadataAPIView(APIView):
    """
    GET /api/rbac/metadata/
    
    Returns RBAC choices and metadata for frontend UI.
    Includes role choices, permission type choices, etc.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from Departments.models import (
                EventDepartmentStaffAssignment,
                ModelPermission,
            )
            
            return Response({
                "roles": [
                    {"value": choice[0], "label": choice[1]}
                    for choice in EventDepartmentStaffAssignment.ROLE_CHOICES
                ],
                "permission_types": [
                    {"value": choice[0], "label": choice[1]}
                    for choice in ModelPermission.PERMISSION_TYPE_CHOICES
                ],
            })
        except Exception as e:
            return Response(
                {"detail": "Error fetching RBAC metadata", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
