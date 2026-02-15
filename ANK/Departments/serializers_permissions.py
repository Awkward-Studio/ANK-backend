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
        
        # Try to find event_department if not provided
        if not event_department:
            # For Guest model, try to find event through EventRegistration
            if model_class.__name__ == 'Guest':
                from Events.models.event_registration_model import EventRegistration
                # Try to get event from request context if available
                request = self.context.get('request')
                event_id = None
                if request:
                    # Check query params for event
                    event_id = request.query_params.get('event')
                    # Or check if there's an event in the URL
                    if not event_id and hasattr(request, 'resolver_match') and request.resolver_match:
                        event_id = request.resolver_match.kwargs.get('event_id') or request.resolver_match.kwargs.get('event_pk')
                
                # If no event from request, find from EventRegistration
                if not event_id:
                    reg = EventRegistration.objects.filter(guest=instance).select_related('event').first()
                    if reg:
                        event = reg.event
                    else:
                        event = None
                else:
                    from Events.models.event_model import Event
                    try:
                        event = Event.objects.get(id=event_id)
                    except:
                        event = None
                
                if event:
                    # For staff: get from staff assignments
                    if user.role == 'staff':
                        from Departments.models import EventDepartment
                        event_department = EventDepartment.objects.filter(
                            event=event,
                            staff_assignments__user=user
                        ).first()
                    # For department_head: get from their department
                    elif user.role == 'department_head' and user.department:
                        from Departments.models import EventDepartment
                        event_department = EventDepartment.objects.filter(
                            event=event,
                            department=user.department
                        ).first()
        
        # If we have an event_department, we can check granular field permissions
        if event_department:
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
                # Don't mask ID or system fields
                if field_name in ['id', 'created_at', 'updated_at', 'event', 'event_department']:
                    continue
                
                # Only mask if field is not in readable_fields set
                if field_name not in readable_fields:
                    # Mask the value (Ghosting UX) - even if it's None or empty
                    val = ret[field_name]
                    if isinstance(val, (int, float, Decimal)):
                        ret[field_name] = 0
                    elif isinstance(val, bool):
                        ret[field_name] = False
                    elif val is None or val == "":
                        ret[field_name] = "********"
                    else:
                        ret[field_name] = "********"
        elif user.role == 'staff':
            # Staff without event_department should see nothing (no access)
            # Mask all fields except ID
            for field_name in ret.keys():
                if field_name not in ['id']:
                    val = ret[field_name]
                    if isinstance(val, (int, float, Decimal)):
                        ret[field_name] = 0
                    elif isinstance(val, bool):
                        ret[field_name] = False
                    elif val is not None:
                        ret[field_name] = "********"
        elif user.role == 'department_head' and not event_department:
            # Department head without event_department context - check if they have model access
            # If no model access, mask all fields
            from Departments.models import DepartmentModelAccess
            dept = user.department
            if dept:
                model_type = ContentType.objects.get_for_model(model_class)
                has_access = DepartmentModelAccess.objects.filter(
                    department=dept,
                    content_type=model_type,
                    can_read=True
                ).exists()
                if not has_access:
                    # No model access - mask all fields except ID
                    for field_name in ret.keys():
                        if field_name not in ['id']:
                            val = ret[field_name]
                            if isinstance(val, (int, float, Decimal)):
                                ret[field_name] = 0
                            elif isinstance(val, bool):
                                ret[field_name] = False
                            elif val is not None:
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
            
            # Try to find event_department if not in context (for Guest model)
            if not event_department and user and self.Meta.model.__name__ == 'Guest':
                from Events.models.event_registration_model import EventRegistration
                reg = EventRegistration.objects.filter(guest=self.instance).select_related('event').first()
                if reg:
                    event = reg.event
                    if user.role == 'staff':
                        from Departments.models import EventDepartment
                        event_department = EventDepartment.objects.filter(
                            event=event,
                            staff_assignments__user=user
                        ).first()
                    elif user.role == 'department_head' and user.department:
                        from Departments.models import EventDepartment
                        event_department = EventDepartment.objects.filter(
                            event=event,
                            department=user.department
                        ).first()
            
            if user and user.role not in ['super_admin', 'admin'] and event_department:
                model_type = ContentType.objects.get_for_model(self.Meta.model)
                # Check write permissions for each field being updated
                for field_name in attrs.keys():
                    # Skip read-only fields
                    if field_name in getattr(self.Meta, 'read_only_fields', []):
                        continue
                    
                    # Check if user has write permission for this field
                    has_write = PermissionChecker.can_access_field(
                        user, event_department, self.Meta.model, 
                        field_name, permission='write'
                    )
                    
                    if not has_write:
                        # Check if they have read permission (to give a better error message)
                        has_read = PermissionChecker.can_access_field(
                            user, event_department, self.Meta.model, 
                            field_name, permission='read'
                        )
                        if has_read:
                            raise serializers.ValidationError(
                                {field_name: "You don't have write permission for this field (read-only)"}
                            )
                        else:
                            raise serializers.ValidationError(
                                {field_name: "You don't have permission to access this field"}
                            )
            elif user and user.role not in ['super_admin', 'admin'] and not event_department:
                # User doesn't have event_department context - block all writes for staff
                if user.role == 'staff':
                    raise serializers.ValidationError(
                        {"detail": "You don't have permission to update this resource"}
                    )
        return attrs
