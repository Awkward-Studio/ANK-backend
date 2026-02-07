from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.conf import settings
from docs.serializers import (
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    LogoutRequestSerializer,
)
from Staff.models import User
from Staff.serializers import (
    UserSerializer,
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
)
from Events.models.event_model import Event
from Events.serializers.event_serializers import EventSerializer
from Events.models.session_model import Session
from Events.serializers.session_serializers import SessionSerializer
from django.contrib.auth import authenticate, login, logout
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

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)
from django.contrib.auth import login, logout


def is_jwt_mode():
    """Reliable check for JWT mode (avoids weird truthy string bugs)"""
    return bool(settings.USE_JWT)


# ─── Register ────────────────────────────────────────────────────────────────


@extend_schema(
    request=RegisterSerializer,
    responses={201: RegisterSerializer},
    description="Register a new user; returns JWT tokens (if enabled) and/or sets session cookie.",
    tags=["Authentication"],
)
class RegisterView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def post(self, request):
        try:
            ser = RegisterSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            user = ser.save()
            user_data = UserSerializer(user).data

            if getattr(settings, "USE_JWT", False):
                refresh = RefreshToken.for_user(user)
                tokens = {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
                return Response(
                    {
                        "user": user_data,
                        "tokens": tokens,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                login(request, user)
                return Response(
                    {
                        "user": user_data,
                        "detail": "Registration successful, session started.",
                    },
                    status=status.HTTP_201_CREATED,
                )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Registration failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Login ───────────────────────────────────────────────────────────────────


class EmailSessionLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SessionLoginResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    user = UserSerializer()


@extend_schema(
    request=EmailSessionLoginSerializer,
    responses={
        200: SessionLoginResponseSerializer,
        400: OpenApiResponse(description="Invalid credentials or missing fields"),
    },
    description="Login using email and password. Returns tokens (JWT) or sets session cookie (SessionAuth).",
    tags=["Authentication"],
)
class LoginView(GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = []
    serializer_class = EmailSessionLoginSerializer

    def post(self, request, *args, **kwargs):
        print("====== HITTING CUSTOM LOGIN VIEW ======")

        print(settings.USE_JWT)

        # print("***** Custom LoginView CALLED *****")
        ser = self.serializer_class(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        email = ser.validated_data["email"]
        password = ser.validated_data["password"]

        user = authenticate(request, email=email, password=password)
        if user is not None:
            user_data = UserSerializer(user).data
            if settings.USE_JWT:
                refresh = RefreshToken.for_user(user)
                tokens = {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
                return Response(
                    {
                        "user": user_data,
                        "tokens": tokens,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                login(request, user)
                return Response(
                    {
                        "detail": "Login successful",
                        "user": user_data,
                    },
                    status=status.HTTP_200_OK,
                )
        else:
            return Response(
                {"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )


# ─── Token Refresh (JWT only) ────────────────────────────────────────────────


@extend_schema(
    request=TokenRefreshRequestSerializer,
    responses={200: TokenRefreshResponseSerializer},
    description="Refresh access token (JWT only)",
    tags=["Authentication"],
)
class RefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        if not getattr(settings, "USE_JWT", False):
            return Response(
                {"detail": "Token refresh not enabled with session authentication."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().post(request, *args, **kwargs)


# ─── Logout ──────────────────────────────────────────────────────────────────


@extend_schema(
    request=LogoutRequestSerializer,
    responses={
        205: OpenApiResponse(description="Refresh token blacklisted, session cleared")
    },
    description="Logout (JWT: blacklist refresh token, Session: clear session)",
    tags=["Authentication"],
)
class LogoutView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LogoutRequestSerializer

    def post(self, request):
        try:
            # JWT mode: blacklist refresh token if provided
            if getattr(settings, "USE_JWT", False):
                refresh_token = request.data.get("refresh")
                if refresh_token:
                    try:
                        token = RefreshToken(refresh_token)
                        token.blacklist()
                    except (TokenError, InvalidToken) as jwt_error:
                        return Response(
                            {"detail": "Invalid token", "error": str(jwt_error)},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            # Always try to logout session
            try:
                logout(request)
            except Exception:
                pass

            return Response(
                {"detail": "Logged out and token blacklisted (if provided)"},
                status=status.HTTP_205_RESET_CONTENT,
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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
            response=EventSerializer(many=True),
            description="List all events assigned to a given user",
            tags=["User Assigned Events"],
        )
    }
)
class UserAssignedEventsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            # Use EventDepartmentStaffAssignment (new RBAC system)
            from Departments.permissions import PermissionChecker
            events = PermissionChecker.get_user_accessible_events(user)
            return Response(EventSerializer(events, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing assigned events", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@document_api_view(
    {
        "get": doc_list(
            response=SessionSerializer(many=True),
            description="List all sessions assigned to a given user",
            tags=["User Assigned Sessions"],
        )
    }
)
class UserAssignedSessionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            # Use EventDepartmentStaffAssignment (new RBAC system)
            from Departments.permissions import PermissionChecker
            sessions = PermissionChecker.get_user_accessible_sessions(user)
            return Response(SessionSerializer(sessions, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing assigned sessions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
