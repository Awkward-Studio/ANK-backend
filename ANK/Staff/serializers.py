from rest_framework import serializers
from Staff.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import (
    extend_schema_serializer,
)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.department:
            from Departments.serializers import DepartmentSerializer
            ret["department"] = DepartmentSerializer(instance.department).data
        return ret

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "name",
            "contact_phone",
            "role",
            "department",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        pwd = validated_data.pop("password", None)
        role = validated_data.pop("role", "staff")
        department = validated_data.pop("department", None)

        user = User(**validated_data, role=role, department=department)
        if pwd:
            user.set_password(pwd)
        else:
            user.set_unusable_password()
        user.save()

        return user

    def update(self, instance, validated_data):
        # Handle password separately - it needs to be hashed
        password = validated_data.pop("password", None)
        
        # Update all other fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        
        # If password is provided and not empty, hash it
        # Empty string means don't update password
        if password is not None and password != "":
            instance.set_password(password)
        
        # Save the instance
        instance.save()
        
        return instance


@extend_schema_serializer(component_name="TokenObtainPair")
class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):

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
