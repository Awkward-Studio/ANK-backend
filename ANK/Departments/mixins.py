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
        user = request.user
        
        # If object has event, get event_department from user's assignment
        if obj and hasattr(obj, 'event'):
            event = obj.event
            # For staff: get from staff assignments
            if user.role == 'staff':
                event_dept = EventDepartment.objects.filter(
                    event=event,
                    staff_assignments__user=user
                ).first()
                return event_dept
            # For department_head: get from their department
            elif user.role == 'department_head' and user.department:
                event_dept = EventDepartment.objects.filter(
                    event=event,
                    department=user.department
                ).first()
                return event_dept
        
        # Try to get event from URL params (for event-scoped views)
        event_id = request.resolver_match.kwargs.get('pk') or request.resolver_match.kwargs.get('event_pk')
        if event_id:
            try:
                from Events.models.event_model import Event
                event = Event.objects.get(id=event_id)
                # For staff: get from staff assignments
                if user.role == 'staff':
                    event_dept = EventDepartment.objects.filter(
                        event=event,
                        staff_assignments__user=user
                    ).first()
                    return event_dept
                # For department_head: get from their department
                elif user.role == 'department_head' and user.department:
                    event_dept = EventDepartment.objects.filter(
                        event=event,
                        department=user.department
                    ).first()
                    return event_dept
            except:
                pass
        
        # For Guest model: try to find event through EventRegistration
        if obj and hasattr(obj, 'events'):
            # Guest has M2M relationship with events through EventRegistration
            # Get first event this guest is registered for
            from Events.models.event_registration_model import EventRegistration
            reg = EventRegistration.objects.filter(guest=obj).select_related('event').first()
            if reg:
                event = reg.event
                # For staff: get from staff assignments
                if user.role == 'staff':
                    event_dept = EventDepartment.objects.filter(
                        event=event,
                        staff_assignments__user=user
                    ).first()
                    return event_dept
                # For department_head: get from their department
                elif user.role == 'department_head' and user.department:
                    event_dept = EventDepartment.objects.filter(
                        event=event,
                        department=user.department
                    ).first()
                    return event_dept
        
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
        # Determine base queryset
        if hasattr(self, 'get_base_queryset'):
            qs = self.get_base_queryset()
        elif hasattr(super(), 'get_queryset'):
            qs = super().get_queryset()
        else:
            # Fallback for APIView without explicit base
            model = getattr(self, 'model', None)
            if model:
                qs = model.objects.all()
            else:
                raise AttributeError(
                    f"{self.__class__.__name__} must define 'get_base_queryset()' or 'model' "
                    "when using DepartmentAccessMixin with APIView."
                )
        
        user = self.request.user
        if user.role in ['super_admin', 'admin']:
            return qs  # No filtering
        
        # Everyone sees the full event list if it's the Event model, 
        # BUT staff only see assigned events (as per user instruction).
        if qs.model.__name__ == 'Event':
            if user.role == 'staff':
                return PermissionChecker.get_user_accessible_events(user)
            # Admin, super_admin, and department_head see all events
            return qs
        
        if user.role == 'department_head':
            # Dept heads see all instances of models their department has access to.
            # "events are not associated with departments" - filtering is purely model-based.
            dept = user.department
            if dept:
                from django.contrib.contenttypes.models import ContentType
                model_type = ContentType.objects.get_for_model(qs.model)
                has_access = DepartmentModelAccess.objects.filter(
                    department=dept,
                    content_type=model_type,
                    can_read=True
                ).exists()
                
                if has_access:
                    return qs
                else:
                    return qs.none()
            return qs.none()
        
        # Staff: Filter models by the events they are assigned to.
        # Check if the model has an 'event' field
        if hasattr(qs.model, 'event'):
            # Filter by events user has access to
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            if accessible_events.exists():
                return qs.filter(event__in=accessible_events)
            else:
                return qs.none()
        
        # For Session model, filter through event relationship
        if qs.model.__name__ == 'Session':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(event__in=accessible_events)
        
        # For SessionRegistration, filter through session -> event
        if qs.model.__name__ == 'SessionRegistration':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            return qs.filter(session__event__in=accessible_events)
        
        # For Guest model, staff only see guests from accessible events.
        if qs.model.__name__ == 'Guest':
            accessible_events = PermissionChecker.get_user_accessible_events(user)
            if accessible_events.exists():
                return qs.filter(events__in=accessible_events).distinct()
            else:
                return qs.none()
        
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
        
        return qs
    
    def get_serializer_context(self):
        """Add event_department to serializer context."""
        context = {}
        if hasattr(super(), 'get_serializer_context'):
            context = super().get_serializer_context()
        
        # Ensure 'request' is always in context for PermissionAwareSerializer
        if 'request' not in context:
            context['request'] = self.request
            
        # Try to get object from various sources
        obj = None
        # For detail views, try to get the object
        if hasattr(self, 'get_object'):
            try:
                obj = self.get_object()
            except:
                pass
        # If no object from get_object, try to get from kwargs (for detail views)
        if not obj and hasattr(self.request, 'resolver_match') and self.request.resolver_match:
            pk = self.request.resolver_match.kwargs.get('pk')
            if pk and hasattr(self, 'get_queryset'):
                try:
                    qs = self.get_queryset()
                    obj = qs.filter(pk=pk).first()
                except:
                    pass
        
        context['event_department'] = self.get_event_department(self.request, obj)
        return context
