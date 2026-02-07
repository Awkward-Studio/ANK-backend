"""
Permission-aware serializer base class.
"""
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from Departments.models import ModelPermission
from Departments.permissions import PermissionChecker


class PermissionAwareSerializer(serializers.ModelSerializer):
    """
    Base serializer that filters fields based on ModelPermission.
    """
    
    def get_fields(self):
        """
        Filter fields based on user permissions.
        """
        fields = super().get_fields()
        request = self.context.get('request')
        event_department = self.context.get('event_department')
        
        if not request or not event_department:
            return fields
        
        user = request.user
        if user.role == 'super_admin':
            return fields
        
        # Get allowed fields for this user + event_department + model
        model_type = ContentType.objects.get_for_model(self.Meta.model)
        
        # Get union of permissions across all user's event_departments for this event
        if hasattr(self.instance, 'event') if self.instance else False:
            allowed_fields = PermissionChecker.get_user_allowed_fields(
                user, self.instance.event, self.Meta.model
            )
        else:
            # Fallback to single event_department
            permissions = ModelPermission.objects.filter(
                user=user,
                event_department=event_department,
                content_type=model_type
            ).values_list('field_name', flat=True)
            allowed_fields = set(permissions)
        
        # If None (super_admin) or empty set, handle appropriately
        if allowed_fields is None:
            return fields  # All fields
        
        if not allowed_fields:
            # No permissions - return empty dict (user sees nothing)
            return {}
        
        # Filter fields - keep SerializerMethodField fields (computed fields)
        filtered_fields = {}
        for field_name, field in fields.items():
            # Always include SerializerMethodField (computed fields)
            if isinstance(field, serializers.SerializerMethodField):
                filtered_fields[field_name] = field
            elif field_name in allowed_fields:
                filtered_fields[field_name] = field
        
        return filtered_fields
    
    def validate(self, attrs):
        """
        Check write permissions for fields being updated.
        """
        if self.instance:  # Update operation
            request = self.context.get('request')
            event_department = self.context.get('event_department')
            user = request.user if request else None
            
            if user and user.role != 'super_admin' and event_department:
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
