from rest_framework import serializers
from Guest.models import Guest, GuestField


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = "__all__"

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request", None)
        user = getattr(request, "user", None)

        # if no user or user has no allowed_guest_fields,
        # default to only id & name
        if not hasattr(user, "allowed_guest_fields"):
            allowed = {"id", "name"}
        else:
            # logged-in staff → id, name, plus whatever they're allowed
            allowed = {"id", "name"} | {
                gf.name for gf in user.allowed_guest_fields.all()
            }

        # prune out disallowed fields
        return {fname: f for fname, f in fields.items() if fname in allowed}


class GuestFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestField
        fields = ["id", "name", "label"]
