from rest_framework import serializers
from Guest.models import Guest, GuestField


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = "__all__"

    def get_fields(self):
        fields = super().get_fields()
        user = self.context["request"].user

        # Always let them see 'id' & 'name'
        allowed = {"id", "name"} | {gf.name for gf in user.allowed_guest_fields.all()}

        # Remove disallowed fields
        for fname in list(fields):
            if fname not in allowed:
                fields.pop(fname)
        return fields


class GuestFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestField
        fields = ["id", "name", "label"]
