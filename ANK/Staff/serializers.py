from rest_framework import serializers
from Staff.models import User, GuestField
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class UserSerializer(serializers.ModelSerializer):
    # show and accept GuestField PKs
    allowed_guest_fields = serializers.PrimaryKeyRelatedField(
        many=True, queryset=GuestField.objects.all()
    )

    class Meta:
        model = User
        fields = "__all__"


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
        # create with email as username
        user = User(
            email=validated_data["email"],
            username=validated_data["email"],
            name=validated_data.get("name", ""),
            contact_phone=validated_data.get("contact_phone", ""),
            role="staff",  # default role for new users
        )
        user.set_password(validated_data["password"])
        user.save()
        return user

    def to_representation(self, instance):
        """After create, also return tokens."""
        ret = super().to_representation(instance)
        refresh = RefreshToken.for_user(instance)
        ret.update(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )
        return ret
