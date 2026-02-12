from rest_framework import serializers
from Guest.models import Guest, GuestField
from Departments.serializers_permissions import PermissionAwareSerializer


class GuestSerializer(PermissionAwareSerializer, serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = "__all__"

    # def get_fields(self):
    #     fields = super().get_fields()
    #     # Require event to be passed in context!
    #     event = self.context.get("event", None)
    #     user = self.context.get("user", None)
    #     # Default: only id/name if not enough info
    #     allowed = {"id", "name"}
    #     if user and event:
    #         from Events.models.field_permissions import UserEventGuestFieldPermission
    #         field_perms = UserEventGuestFieldPermission.objects.filter(user=user, event=event)
    #         allowed = allowed | {perm.guest_field.name for perm in field_perms.select_related("guest_field")}
    #     # Only include allowed fields
    #     return {fname: f for fname, f in fields.items() if fname in allowed}


class GuestFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestField
        fields = ["id", "name", "label"]


class RestrictedGuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        # Explicitly list all fields except the M2M ones:
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "city",
            "nationality",
            "photo_id",
        ]
