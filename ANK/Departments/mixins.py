"""
View mixins for RBAC enforcement.
"""
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from Departments.models import EventDepartment, DepartmentModelAccess
from Departments.permissions import PermissionChecker


class DepartmentAccessMixin:
    """
    Mixin for views to filter querysets based on department assignments.
    """
    
    def get_event_department(self, request, obj=None):
        """
        Determine event_department from request/object.
        
        Args:
            request: Request object
            obj: Model instance (if available)
            
        Returns:
            EventDepartment or None
        """
        # If object has event, get event_department from user's assignment
        if obj and hasattr(obj, 'event'):
            event = obj.event
            # Get user's event_department for this event (prefer first one)
            event_dept = EventDepartment.objects.filter(
                event=event,
                staff_assignments__user=request.user
            ).first()
            return event_dept
        
        # Try to get event from URL params (for event-scoped views)
        event_id = request.resolver_match.kwargs.get('pk') or request.resolver_match.kwargs.get('event_pk')
        if event_id:
            try:
                from Events.models.event_model import Event
                event = Event.objects.get(id=event_id)
                event_dept = EventDepartment.objects.filter(
                    event=event,
                    staff_assignments__user=request.user
                ).first()
                return event_dept
            except:
                pass
        
        # Try to get from query params
        event_department_id = request.query_params.get('event_department')
        if event_department_id:
            try:
                return EventDepartment.objects.get(id=event_department_id)
            except EventDepartment.DoesNotExist:
                pass
        
        # For list views, may need to handle differently
        return None
    
    def get_queryset(self):
        """
        Filter queryset based on user role and assignments.
        """
        qs = super().get_queryset()
        user = self.request.user
        
        if user.role == 'super_admin':
            return qs  # No filtering
        
        if user.role == 'department_head':
            # Department heads see all events, but filtered by their department's models
            dept = user.department
            if dept:
                # Get models this department can access
                from django.contrib.contenttypes.models import ContentType
                allowed_model_types = DepartmentModelAccess.objects.filter(
                    department=dept,
                    can_read=True
                ).values_list('content_type', flat=True)
                
                # Filter queryset to only include these model types
                # This works if the queryset model has a content_type field
                # For most cases, we'll filter at the model level
                model_type = ContentType.objects.get_for_model(qs.model)
                if model_type.id in allowed_model_types:
                    return qs
                else:
                    return qs.none()
            return qs
        
        # Staff: Only see resources from events they're assigned to via EventDepartmentStaffAssignment
        # Check if the model has an 'event' field
        if hasattr(qs.model, 'event'):
            # Filter by events user has access to
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event__in=accessible_events)
        
        # For Session model, filter through event relationship
        if qs.model.__name__ == 'Session':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event__in=accessible_events)
        
        # For SessionRegistration, filter through session -> event
        if qs.model.__name__ == 'SessionRegistration':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(session__event__in=accessible_events)
        
        # For Guest model, filter through EventRegistration relationship
        if qs.model.__name__ == 'Guest':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(events__in=accessible_events).distinct()
        
        # For EventRegistration, filter through event
        if qs.model.__name__ == 'EventRegistration':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event__in=accessible_events)
        
        # For TravelDetail and Accommodation, filter through event
        if qs.model.__name__ in ['TravelDetail', 'Accommodation']:
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event__in=accessible_events)
        
        # For BudgetLineItem, filter through event_department -> event
        if qs.model.__name__ == 'BudgetLineItem':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event_department__event__in=accessible_events)
        
        # For models without direct event relationship, check through related models
        # This is handled per-model basis
        return qs
    
    def get_serializer_context(self):
        """Add event_department to serializer context."""
        context = super().get_serializer_context()
        obj = None
        if hasattr(self, 'get_object'):
            try:
                obj = self.get_object()
            except:
                pass
        context['event_department'] = self.get_event_department(self.request, obj)
        return context
    
    def post(self, request, *args, **kwargs):
        """Check create permissions before allowing POST."""
        event_department = self.get_event_department(request)
        if event_department:
            if not PermissionChecker.can_access_model(
                request.user, event_department, self.get_queryset().model
            ):
                return Response(
                    {"detail": "You don't have permission to create this resource"},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().post(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):
        """Check write permissions before allowing PUT."""
        obj = self.get_object()
        event_department = self.get_event_department(request, obj)
        if event_department:
            if not PermissionChecker.can_access_model(
                request.user, event_department, self.get_queryset().model
            ):
                return Response(
                    {"detail": "You don't have permission to update this resource"},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().put(request, *args, **kwargs)
    
    def patch(self, request, *args, **kwargs):
        """Check write permissions before allowing PATCH."""
        obj = self.get_object()
        event_department = self.get_event_department(request, obj)
        if event_department:
            if not PermissionChecker.can_access_model(
                request.user, event_department, self.get_queryset().model
            ):
                return Response(
                    {"detail": "You don't have permission to update this resource"},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().patch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        """Check delete permissions."""
        obj = self.get_object()
        event_department = self.get_event_department(request, obj)
        if event_department:
            # Check if user can delete (typically requires write permission)
            from Departments.models import DepartmentModelAccess
            from django.contrib.contenttypes.models import ContentType
            
            dept = event_department.department
            model_type = ContentType.objects.get_for_model(self.get_queryset().model)
            
            can_delete = DepartmentModelAccess.objects.filter(
                department=dept,
                content_type=model_type,
                can_delete=True
            ).exists()
            
            if not can_delete and request.user.role != 'super_admin':
                return Response(
                    {"detail": "You don't have permission to delete this resource"},
                    status=status.HTTP_403_FORBIDDEN
                )
        return super().delete(request, *args, **kwargs)
