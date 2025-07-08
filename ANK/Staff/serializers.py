from rest_framework import serializers
from Staff.models import User, GuestField
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    allowed_guest_fields = serializers.PrimaryKeyRelatedField(
        many=True, queryset=GuestField.objects.all(), required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "name",
            "contact_phone",
            "role",
            "allowed_guest_fields",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        agf = validated_data.pop("allowed_guest_fields", [])
        pwd = validated_data.pop("password", None)

        user = User(**validated_data, role=validated_data.get("role", "staff"))
        if pwd:
            user.set_password(pwd)
        else:
            user.set_unusable_password()
        user.save()

        if agf:
            user.allowed_guest_fields.set(agf)
        return user

    def update(self, instance, validated_data):
        agf = validated_data.pop("allowed_guest_fields", None)
        pwd = validated_data.pop("password", None)

        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if pwd:
            instance.set_password(pwd)
        instance.save()

        if agf is not None:
            instance.allowed_guest_fields.set(agf)
        return instance


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    # if you've set USERNAME_FIELD="email", you don't need to override much
    # but you can customize the response here if desired

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # add custom claims if you like:
        token["role"] = user.role
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "name",
            "contact_phone",
        ]

    def create(self, validated_data):
        pwd = validated_data.pop("password")
        user = User(
            email=validated_data["email"],
            name=validated_data.get("name", ""),
            contact_phone=validated_data.get("contact_phone", ""),
            role="staff",
        )
        user.set_password(pwd)
        user.save()
        return user

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        refresh = RefreshToken.for_user(instance)
        ret.update(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )
        return ret
