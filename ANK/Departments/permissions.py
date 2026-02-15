"""
Permission checking utilities for RBAC system.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from Departments.models import DepartmentModelAccess, ModelPermission, EventDepartment


class PermissionChecker:
    """
    Utility class for checking permissions.
    """
    
    @staticmethod
    def can_access_model(user, event_department, model_class):
        """
        Check if user can access a model type in this event department.
        
        Args:
            user: User instance
            event_department: EventDepartment instance
            model_class: Model class to check access for
            
        Returns:
            bool: True if user can access the model, False otherwise
        """
        if user.role in ['super_admin', 'admin']:
            return True
        
        dept = event_department.department
        model_type = ContentType.objects.get_for_model(model_class)
        
        return DepartmentModelAccess.objects.filter(
            department=dept,
            content_type=model_type,
            can_read=True
        ).exists()
    
    @staticmethod
    def can_access_field(user, event_department, model_class, field_name, permission='read'):
        """
        Check if user can access a specific field.
        
        Args:
            user: User instance
            event_department: EventDepartment instance
            model_class: Model class
            field_name: Field name to check
            permission: 'read', 'write', or 'read_write'
            
        Returns:
            bool: True if user has the required permission, False otherwise
        """
        if user.role in ['super_admin', 'admin']:
            return True
        
        model_type = ContentType.objects.get_for_model(model_class)
        
        # Check for exact permission match or read_write
        permission_types = [permission]
        if permission == 'read':
            permission_types.append('read_write')
        elif permission == 'write':
            permission_types.append('read_write')
        
        return ModelPermission.objects.filter(
            user=user,
            event_department=event_department,
            content_type=model_type,
            field_name=field_name,
            permission_type__in=permission_types
        ).exists()
    
    @staticmethod
    def get_user_allowed_fields(user, event, model_class):
        """
        Get union of all allowed fields across all user's event_departments for this event.
        
        Args:
            user: User instance
            event: Event instance
            model_class: Model class to get fields for
            
        Returns:
            set: Set of allowed field names, or None if super_admin/admin (all fields)
        """
        if user.role in ['super_admin', 'admin']:
            return None  # All fields
        
        # For department heads: check their department's model access
        if user.role == 'department_head' and user.department:
            # Get event departments for this department
            event_departments = EventDepartment.objects.filter(
                event=event,
                department=user.department
            )
            
            if not event_departments.exists():
                # Check if department has model-level access (but no event_department yet)
                model_type = ContentType.objects.get_for_model(model_class)
                has_model_access = DepartmentModelAccess.objects.filter(
                    department=user.department,
                    content_type=model_type,
                    can_read=True
                ).exists()
                
                if has_model_access:
                    # Department has model access, return None to show all fields
                    # (field-level permissions will be checked separately if they exist)
                    return None
                else:
                    return set()  # No access
            
            # Get field-level permissions if they exist
            model_type = ContentType.objects.get_for_model(model_class)
            permissions = ModelPermission.objects.filter(
                user=user,
                event_department__in=event_departments,
                content_type=model_type
            ).values_list('field_name', flat=True).distinct()
            
            # If no field-level permissions, check model access
            if not permissions.exists():
                has_model_access = DepartmentModelAccess.objects.filter(
                    department=user.department,
                    content_type=model_type,
                    can_read=True
                ).exists()
                if has_model_access:
                    return None  # All fields accessible at model level
            
            return set(permissions)
        
        # For staff: only from event_departments they're assigned to
        event_departments = EventDepartment.objects.filter(
            event=event,
            staff_assignments__user=user
        )
        
        if not event_departments.exists():
            return set()  # No access
        
        model_type = ContentType.objects.get_for_model(model_class)
        permissions = ModelPermission.objects.filter(
            user=user,
            event_department__in=event_departments,
            content_type=model_type
        ).values_list('field_name', flat=True).distinct()
        
        return set(permissions)
    
    @staticmethod
    def get_user_accessible_events(user):
        """
        Get all events a user can access.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Events the user can access
        """
        from Events.models.event_model import Event
        
        if user.role in ['super_admin', 'admin']:
            return Event.objects.all()
        
        if user.role == 'department_head':
            # Department heads see all events, but filtered by their department's model access
            # For now, return all events (model filtering happens at queryset level)
            return Event.objects.all()
        
        # Staff: Only events via EventDepartmentStaffAssignment
        return Event.objects.filter(
            event_departments__staff_assignments__user=user
        ).distinct()
    
    @staticmethod
    def get_user_accessible_sessions(user):
        """
        Get all sessions a user can access.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Sessions the user can access
        """
        from Events.models.session_model import Session
        
        if user.role in ['super_admin', 'admin']:
            return Session.objects.all()
        
        if user.role == 'department_head':
            # Department heads see all sessions
            return Session.objects.all()
        
        # Staff: Sessions belong to events, so event access = session access
        return Session.objects.filter(
            event__event_departments__staff_assignments__user=user
        ).distinct()


def get_user_permissions(user, event_department):
    """
    Get all permissions for a user in an event department.
    Cached for 1 hour.
    
    Args:
        user: User instance
        event_department: EventDepartment instance
        
    Returns:
        list: List of tuples (content_type.model, field_name, permission_type)
    """
    cache_key = f"perms:{user.id}:{event_department.id}"
    perms = cache.get(cache_key)
    
    if perms is None:
        perms = ModelPermission.objects.filter(
            user=user,
            event_department=event_department
        ).select_related('content_type').values_list(
            'content_type__model', 'field_name', 'permission_type'
        )
        cache.set(cache_key, list(perms), timeout=3600)
    
    return perms


def invalidate_permission_cache(sender, instance, **kwargs):
    """Invalidate cache when permissions change."""
    cache_key = f"perms:{instance.user.id}:{instance.event_department.id}"
    cache.delete(cache_key)
