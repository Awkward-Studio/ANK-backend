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

from utils.swagger import (
    document_api_view,
    doc_list,
    doc_create,
    doc_retrieve,
    doc_update,
    doc_destroy,
    query_param,
)


# ─── Register ────────────────────────────────────────────────────────────────


@document_api_view(
    {
        "post": doc_create(
            request=RegisterSerializer,
            response=RegisterSerializer,
            description="Register a new user; returns JWT tokens",
            tags=["Authentication"],
        )
    }
)
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


# For login/refresh, annotate the POST method directly
TokenObtainPairView.post = doc_create(
    request=EmailTokenObtainPairSerializer,
    response=EmailTokenObtainPairSerializer,
    description="Obtain JWT access & refresh tokens",
    tags=["Authentication"],
)(TokenObtainPairView.post)

TokenRefreshView.post = doc_create(
    request=serializers.Serializer,  # expects {"refresh": "..."}
    response=serializers.Serializer,  # returns {"access": "..."}
    description="Refresh access token",
    tags=["Authentication"],
)(TokenRefreshView.post)


@document_api_view(
    {
        "post": doc_destroy(
            description="Logout and blacklist the provided refresh token",
            tags=["Authentication"],
        )
    }
)
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


@document_api_view(
    {
        "get": doc_list(
            response=UserSerializer(many=True),
            parameters=[
                query_param("email", "email", False, "Filter by email"),
                query_param("name", "str", False, "Filter by name (contains)"),
                query_param("role", "str", False, "Filter by role (admin or staff)"),
            ],
            description="List all users",
            tags=["Users"],
        ),
        "post": doc_create(
            request=UserSerializer,
            response=UserSerializer,
            description="Create a new user",
            tags=["Users"],
        ),
    }
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
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        except ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error creating user", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_retrieve(
            response=UserSerializer, description="Retrieve a user by ID", tags=["Users"]
        ),
        "put": doc_update(
            request=UserSerializer,
            response=UserSerializer,
            description="Update a user by ID",
            tags=["Users"],
        ),
        "delete": doc_destroy(description="Delete a user by ID", tags=["Users"]),
    }
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


@document_api_view(
    {
        "get": doc_list(
            response=GuestFieldSerializer(many=True),
            parameters=[
                query_param("pk", "uuid", True, "User ID in URL"),
            ],
            description="List allowed guest fields for a user",
            tags=["Guest Fields allowed for User"],
        ),
        "put": doc_update(
            response=GuestFieldSerializer(many=True),
            description="Replace a user’s allowed_guest_fields with provided list",
            tags=["Guest Fields allowed for User"],
        ),
    }
)
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

    def put(self, request, pk):
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
                GuestFieldSerializer(user.allowed_guest_fields.all(), many=True).data,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "detail": "Error updating user’s guest‐field permissions",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "post": doc_create(
            request=serializers.Serializer,  # expects {"guestfield_id": "<uuid>"}
            response=GuestFieldSerializer(many=True),
            description="Add a guest-field to a user’s allowed_guest_fields",
            tags=["Guest Fields allowed for User"],
        )
    }
)
class UserGuestFieldAddAPIView(APIView):
    """
    POST /users/{pk}/guestfields/add/
    Body: { "guestfield_id": "<uuid>" }
    → returns updated list of allowed_guest_fields
    """

    def post(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            gid = request.data.get("guestfield_id")
            if not gid:
                return Response(
                    {"detail": "guestfield_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            field = get_object_or_404(GuestField, pk=gid)
            user.allowed_guest_fields.add(field)
            return Response(
                GuestFieldSerializer(user.allowed_guest_fields.all(), many=True).data,
                status=status.HTTP_200_OK,
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error adding guest-field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "delete": doc_destroy(
            response=GuestFieldSerializer(many=True),
            description="Remove a guest-field from a user’s allowed_guest_fields",
            tags=["Guest Fields allowed for User"],
        )
    }
)
class UserGuestFieldRemoveAPIView(APIView):
    """
    DELETE /users/{pk}/guestfields/{field_pk}/
    → returns updated list of allowed_guest_fields
    """

    def delete(self, request, pk, field_pk):
        try:
            user = get_object_or_404(User, pk=pk)
            field = get_object_or_404(GuestField, pk=field_pk)
            user.allowed_guest_fields.remove(field)
            return Response(
                GuestFieldSerializer(user.allowed_guest_fields.all(), many=True).data,
                status=status.HTTP_200_OK,
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Error removing guest-field", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
