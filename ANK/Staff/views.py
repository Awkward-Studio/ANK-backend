from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from Staff.models import User, GuestField
from Staff.serializers import (
    UserSerializer,
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
)
from Guest.serializers import GuestFieldSerializer

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        try:
            ser = RegisterSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            user_data = ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Registration failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoginView(TokenObtainPairView):
    """
    POST /auth/login/  { "email": "...", "password": "..." }
    →  { "refresh": "...", "access": "..." }
    """

    permission_classes = (AllowAny,)
    serializer_class = EmailTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    """
    POST /auth/refresh/ { "refresh": "..." }
    → { "access": "..." }
    """

    permission_classes = (AllowAny,)


class LogoutView(APIView):
    """
    POST /auth/logout/ { "refresh": "..." }
    → 204 No Content (blacklists the refresh token)
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except KeyError:
            return Response(
                {"detail": "`refresh` field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (TokenError, InvalidToken) as e:
            return Response(
                {"detail": "Invalid token", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": "Logout failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserList(APIView):
    def get(self, request):
        try:
            qs = User.objects.all()
            return Response(UserSerializer(qs, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching users", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            ser = UserSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            user = ser.save()
            if "password" in request.data:
                user.set_password(request.data["password"])
                user.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserDetail(APIView):
    def get(self, request, pk):
        try:
            obj = get_object_or_404(User, pk=pk)
            return Response(UserSerializer(obj).data)
        except Exception as e:
            return Response(
                {"detail": "Error fetching user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            ser = UserSerializer(user, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            user = ser.save()
            if "password" in request.data:
                user.set_password(request.data["password"])
                user.save()
            return Response(UserSerializer(user).data)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error updating user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": "Error deleting user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


#
#  Custom endpoint: manage a User’s allowed_guest_fields
#
class UserGuestFieldAPIView(APIView):
    """
    GET  /users/{pk}/guestfields/     → list this user’s assigned GuestFields
    POST /users/{pk}/guestfields/     → replace that list with the posted IDs
      payload: { "guestfield_ids": [1,2,3] }
    """

    def get(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            fields = user.allowed_guest_fields.all()
            return Response(GuestFieldSerializer(fields, many=True).data)
        except Exception as e:
            return Response(
                {
                    "detail": "Error fetching user’s guest‐field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            ids = request.data.get("guestfield_ids")
            if not isinstance(ids, list):
                return Response(
                    {"detail": "guestfield_ids must be a list of IDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fields = GuestField.objects.filter(id__in=ids)
            user.allowed_guest_fields.set(fields)
            user.save()
            return Response(
                GuestFieldSerializer(user.allowed_guest_fields.all(), many=True).data
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error updating user’s guest‐field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
