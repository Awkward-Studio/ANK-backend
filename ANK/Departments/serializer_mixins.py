from rest_framework import serializers
from Departments.permissions import PermissionChecker

class PermissionAwareMixin:
    """
    Mixin for serializers to enforce field-level permissions.
    Expects 'event_department' in context.
    """
    
    def to_representation(self, instance):
        """
        Mask fields that the user only has 'no access' to.
        If user has 'read' or 'read_write', they see the value.
        If user has NO permission entry for a field, it's masked (Ghosting).
        """
        ret = super().to_representation(instance)
        request = self.context.get('request')
        event_department = self.context.get('event_department')
        
        if not request or not request.user:
            return ret
            
        user = request.user
        
        # Super admins, Admins and Django superusers see everything
        if user.role in ['super_admin', 'admin'] or getattr(user, 'is_superuser', False):
            return ret
            
        # Get permissions for this model and event_department
        model_class = instance._meta.model
        
        # If we have an event_department, we can check granular field permissions
        if event_department:
            from Departments.models import ModelPermission
            from django.contrib.contenttypes.models import ContentType
            
            content_type = ContentType.objects.get_for_model(model_class)
            
            # Get all permissions for this user, event_dept, and model
            perms = ModelPermission.objects.filter(
                user=user,
                event_department=event_department,
                content_type=content_type
            ).values_list('field_name', 'permission_type')
            
            # Map of field -> can_read
            readable_fields = {field for field, ptype in perms if ptype in ['read', 'read_write']}
            
            # Special case for BudgetLineItem which uses its own BudgetFieldPermission model
            if model_class.__name__ == 'BudgetLineItem':
                from Departments.models import BudgetFieldPermission
                budget_perms = set(BudgetFieldPermission.objects.filter(
                    user=user,
                    event_department=event_department
                ).values_list('field_key', flat=True))
                readable_fields.update(budget_perms)

            # Iterate over fields and mask if not readable
            for field_name in ret.keys():
                # Don't mask ID or system fields
                if field_name in ['id', 'created_at', 'updated_at', 'event', 'event_department']:
                    continue
                    
                if field_name not in readable_fields:
                    # Mask the value (Ghosting UX)
                    if isinstance(ret[field_name], (int, float)):
                        ret[field_name] = 0
                    elif isinstance(ret[field_name], bool):
                        ret[field_name] = False
                    else:
                        ret[field_name] = "********"
        
        return ret
