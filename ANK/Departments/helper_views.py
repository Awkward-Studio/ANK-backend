from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from Events.models.event_model import Event
from Departments.models import (
    EventDepartment,
    EventDepartmentStaffAssignment,
    ModelPermission,
    DepartmentModelAccess,
    User,
    Department,
)
from Departments.serializers import (
    EventDepartmentStaffAssignmentSerializer,
    ModelPermissionSerializer,
)
from utils.swagger import (
    document_api_view,
    doc_create,
    query_param,
)


# ─────────────────────────────────────────────────────────────
# Helper Endpoints for RBAC
# ─────────────────────────────────────────────────────────────


@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk assign staff to event-departments for a specific event",
            tags=["RBAC: Helper Endpoints"],
        )
    }
)
class BulkAssignStaffToEventAPIView(APIView):
    """
    POST /api/events/<event_id>/assign-staff/
    
    Bulk assign staff members to event-departments for an event.
    
    Body:
    {
        "assignments": [
            {
                "user_id": "<uuid>",
                "event_department_id": "<uuid>",
                "role": "lead" | "crew"
            },
            ...
        ]
    }
    
    Returns:
    {
        "created": [...],
        "updated": [...],
        "errors": [...]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin, admin, and department_head can assign staff."""
        if request.user.role not in ['super_admin', 'admin', 'department_head']:
            raise PermissionDenied("Only admins and department heads can assign staff.")

    def post(self, request, event_id):
        self.check_permissions(request)
        try:
            event = get_object_or_404(Event, pk=event_id)
            assignments_data = request.data.get('assignments', [])
            
            if not isinstance(assignments_data, list):
                return Response(
                    {"detail": "assignments must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created = []
            updated = []
            errors = []
            
            with transaction.atomic():
                for idx, assignment_data in enumerate(assignments_data):
                    try:
                        user_id = assignment_data.get('user_id')
                        event_dept_id = assignment_data.get('event_department_id')
                        role = assignment_data.get('role', 'crew')
                        
                        if not user_id or not event_dept_id:
                            errors.append({
                                "index": idx,
                                "error": "user_id and event_department_id are required"
                            })
                            continue
                        
                        # Verify event_department belongs to this event
                        event_dept = EventDepartment.objects.filter(
                            id=event_dept_id,
                            event=event
                        ).first()
                        
                        if not event_dept:
                            errors.append({
                                "index": idx,
                                "error": f"EventDepartment {event_dept_id} does not belong to event {event_id}"
                            })
                            continue
                        
                        # Get or create assignment
                        assignment, created_flag = EventDepartmentStaffAssignment.objects.get_or_create(
                            user_id=user_id,
                            event_department_id=event_dept_id,
                            defaults={'role': role}
                        )
                        
                        if not created_flag:
                            # Update existing assignment
                            assignment.role = role
                            assignment.removed_on = None  # Reactivate if removed
                            assignment.save()
                            updated.append({
                                "assignment_id": str(assignment.id),
                                "user_id": str(user_id),
                                "event_department_id": str(event_dept_id),
                                "role": role
                            })
                        else:
                            created.append({
                                "assignment_id": str(assignment.id),
                                "user_id": str(user_id),
                                "event_department_id": str(event_dept_id),
                                "role": role
                            })
                    
                    except Exception as e:
                        errors.append({
                            "index": idx,
                            "error": str(e)
                        })
            
            return Response({
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_processed": len(assignments_data),
                "successful": len(created) + len(updated)
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"detail": "Error bulk assigning staff", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk assign field-level permissions to a user for an event-department",
            tags=["RBAC: Helper Endpoints"],
        )
    }
)
class BulkAssignPermissionsAPIView(APIView):
    """
    POST /api/event-departments/<event_dept_id>/users/<user_id>/bulk-permissions/
    
    Bulk assign field-level permissions to a user for an event-department.
    
    Body:
    {
        "permissions": [
            {
                "content_type_id": <int>,  // ContentType ID for the model
                "field_name": "<str>",     // Field name
                "permission_type": "read" | "write" | "read_write"
            },
            ...
        ]
    }
    
    Returns:
    {
        "created": [...],
        "updated": [...],
        "errors": [...]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin and department_head can assign permissions."""
        if request.user.role not in ['super_admin', 'department_head']:
            raise PermissionDenied("Only super admins and department heads can assign permissions.")

    def post(self, request, event_dept_id, user_id):
        self.check_permissions(request)
        try:
            event_dept = get_object_or_404(EventDepartment, pk=event_dept_id)
            user = get_object_or_404(User, pk=user_id)
            permissions_data = request.data.get('permissions', [])
            
            if not isinstance(permissions_data, list):
                return Response(
                    {"detail": "permissions must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created = []
            updated = []
            errors = []
            
            with transaction.atomic():
                for idx, perm_data in enumerate(permissions_data):
                    try:
                        content_type_id = perm_data.get('content_type_id')
                        field_name = perm_data.get('field_name')
                        permission_type = perm_data.get('permission_type', 'read')
                        
                        if not content_type_id or not field_name:
                            errors.append({
                                "index": idx,
                                "error": "content_type_id and field_name are required"
                            })
                            continue
                        
                        # Validate ContentType
                        try:
                            content_type = ContentType.objects.get(id=content_type_id)
                        except ContentType.DoesNotExist:
                            errors.append({
                                "index": idx,
                                "error": f"ContentType {content_type_id} does not exist"
                            })
                            continue
                        
                        # Validate permission_type
                        if permission_type not in ['read', 'write', 'read_write']:
                            errors.append({
                                "index": idx,
                                "error": f"Invalid permission_type: {permission_type}"
                            })
                            continue
                        
                        # Get or create permission
                        permission, created_flag = ModelPermission.objects.get_or_create(
                            user=user,
                            event_department=event_dept,
                            content_type=content_type,
                            field_name=field_name,
                            defaults={'permission_type': permission_type}
                        )
                        
                        if not created_flag:
                            # Update existing permission
                            permission.permission_type = permission_type
                            permission.save()
                            updated.append({
                                "permission_id": str(permission.id),
                                "content_type": content_type.model,
                                "field_name": field_name,
                                "permission_type": permission_type
                            })
                        else:
                            created.append({
                                "permission_id": str(permission.id),
                                "content_type": content_type.model,
                                "field_name": field_name,
                                "permission_type": permission_type
                            })
                    
                    except ValidationError as ve:
                        errors.append({
                            "index": idx,
                            "error": str(ve)
                        })
                    except Exception as e:
                        errors.append({
                            "index": idx,
                            "error": str(e)
                        })
            
            return Response({
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_processed": len(permissions_data),
                "successful": len(created) + len(updated)
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"detail": "Error bulk assigning permissions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=None,
            response=None,
            description="Bulk create department-model access mappings",
            tags=["RBAC: Helper Endpoints"],
        )
    }
)
class BulkCreateDepartmentModelAccessAPIView(APIView):
    """
    POST /api/departments/<department_id>/bulk-model-access/
    
    Bulk create department-model access mappings.
    
    Body:
    {
        "mappings": [
            {
                "content_type_id": <int>,
                "can_read": true,
                "can_write": false,
                "can_create": false,
                "can_delete": false
            },
            ...
        ]
    }
    
    Returns:
    {
        "created": [...],
        "updated": [...],
        "errors": [...]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def check_permissions(self, request):
        """Only super_admin can manage department-model access."""
        if request.user.role != 'super_admin':
            raise PermissionDenied("Only super admins can manage department-model access.")

    def post(self, request, department_id):
        self.check_permissions(request)
        try:
            department = get_object_or_404(Department, pk=department_id)
            mappings_data = request.data.get('mappings', [])
            
            if not isinstance(mappings_data, list):
                return Response(
                    {"detail": "mappings must be a list"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created = []
            updated = []
            errors = []
            
            with transaction.atomic():
                for idx, mapping_data in enumerate(mappings_data):
                    try:
                        content_type_id = mapping_data.get('content_type_id')
                        
                        if not content_type_id:
                            errors.append({
                                "index": idx,
                                "error": "content_type_id is required"
                            })
                            continue
                        
                        # Validate ContentType
                        try:
                            content_type = ContentType.objects.get(id=content_type_id)
                        except ContentType.DoesNotExist:
                            errors.append({
                                "index": idx,
                                "error": f"ContentType {content_type_id} does not exist"
                            })
                            continue
                        
                        # Get or create mapping
                        mapping, created_flag = DepartmentModelAccess.objects.get_or_create(
                            department=department,
                            content_type=content_type,
                            defaults={
                                'can_read': mapping_data.get('can_read', True),
                                'can_write': mapping_data.get('can_write', False),
                                'can_create': mapping_data.get('can_create', False),
                                'can_delete': mapping_data.get('can_delete', False),
                            }
                        )
                        
                        if not created_flag:
                            # Update existing mapping
                            mapping.can_read = mapping_data.get('can_read', mapping.can_read)
                            mapping.can_write = mapping_data.get('can_write', mapping.can_write)
                            mapping.can_create = mapping_data.get('can_create', mapping.can_create)
                            mapping.can_delete = mapping_data.get('can_delete', mapping.can_delete)
                            mapping.save()
                            updated.append({
                                "mapping_id": str(mapping.id),
                                "content_type": content_type.model
                            })
                        else:
                            created.append({
                                "mapping_id": str(mapping.id),
                                "content_type": content_type.model
                            })
                    
                    except Exception as e:
                        errors.append({
                            "index": idx,
                            "error": str(e)
                        })
            
            return Response({
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_processed": len(mappings_data),
                "successful": len(created) + len(updated)
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"detail": "Error bulk creating department-model access", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
