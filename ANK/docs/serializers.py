from rest_framework import serializers


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ExtraAttendeeInfoSerializer(serializers.Serializer):
    extra_attendee_id = serializers.UUIDField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True, required=False)


class GuestInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True, required=False)
    email = serializers.EmailField()
    city = serializers.CharField(allow_blank=True, required=False)


class EventAttendeeSerializer(serializers.Serializer):
    event_registration_id = serializers.UUIDField()
    guest = GuestInfoSerializer()
    extras = ExtraAttendeeInfoSerializer(many=True)
