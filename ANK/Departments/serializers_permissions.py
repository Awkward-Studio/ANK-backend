"""
Permission-aware serializer base class.
"""
from decimal import Decimal
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from Departments.models import ModelPermission
from Departments.permissions import PermissionChecker


class PermissionAwareSerializer(serializers.ModelSerializer):
    """
    Base serializer that masks unauthorized fields (Ghosting UX).
    """
    
    def to_representation(self, instance):
        """
        Mask fields that the user doesn't have read access to.
        """
        ret = super().to_representation(instance)
        request = self.context.get('request')
        event_department = self.context.get('event_department')
        
        if not request or not request.user:
            return ret
            
        user = request.user
        
        if user.role in ['super_admin', 'admin'] or getattr(user, 'is_superuser', False):
            return ret
            
        # Get allowed fields
        model_class = self.Meta.model
        
        # If we have an event_department, we can check granular field permissions
        if event_department:
            from Departments.models import ModelPermission
            from django.contrib.contenttypes.models import ContentType
            
            content_type = ContentType.objects.get_for_model(model_class)
            
            # Use PermissionChecker to get all readable fields for the user in this event context
            # (Checks both single event_department and global department access)
            readable_fields = PermissionChecker.get_user_allowed_fields(
                user, event_department.event, model_class
            )
            
            if readable_fields is None:
                return ret
            
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
                # Don't mask ID or system fields or already empty/null values
                if field_name in ['id', 'created_at', 'updated_at', 'event', 'event_department'] or ret[field_name] is None:
                    continue
                    
                if field_name not in readable_fields:
                    # Mask the value (Ghosting UX)
                    val = ret[field_name]
                    if isinstance(val, (int, float, Decimal)):
                        ret[field_name] = 0
                    elif isinstance(val, bool):
                        ret[field_name] = False
                    else:
                        ret[field_name] = "********"
        
        return ret
    
    def validate(self, attrs):
        """
        Check write permissions for fields being updated.
        """
        if self.instance:  # Update operation
            request = self.context.get('request')
            event_department = self.context.get('event_department')
            user = request.user if request else None
            
            if user and user.role not in ['super_admin', 'admin'] and event_department:
                model_type = ContentType.objects.get_for_model(self.Meta.model)
                # Check write permissions for each field being updated
                for field_name in attrs.keys():
                    # Skip read-only fields
                    if field_name in getattr(self.Meta, 'read_only_fields', []):
                        continue
                    
                    if not PermissionChecker.can_access_field(
                        user, event_department, self.Meta.model, 
                        field_name, permission='write'
                    ):
                        raise serializers.ValidationError(
                            {field_name: "You don't have write permission for this field"}
                        )
        return attrs
