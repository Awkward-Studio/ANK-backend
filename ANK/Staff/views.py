from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

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

# # ─── Register ────────────────────────────────────────────────────────────────


# @extend_schema(
#     request=RegisterSerializer,
#     responses={201: RegisterSerializer},
#     description="Register a new user; returns JWT tokens",
#     tags=["Authentication"],
# )
# class RegisterView(GenericAPIView):
#     permission_classes = (AllowAny,)
#     serializer_class = RegisterSerializer

#     def post(self, request):
#         try:
#             ser = RegisterSerializer(data=request.data)
#             ser.is_valid(raise_exception=True)
#             user = ser.save()

#             # Generate JWT tokens for the new user
#             refresh = RefreshToken.for_user(user)
#             tokens = {
#                 "refresh": str(refresh),
#                 "access": str(refresh.access_token),
#             }

#             # Serialize user data
#             user_data = UserSerializer(user).data

#             return Response(
#                 {
#                     "user": user_data,
#                     "tokens": tokens,
#                 },
#                 status=status.HTTP_201_CREATED,
#             )
#         except serializers.ValidationError as ve:
#             return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response(
#                 {"detail": "Registration failed", "error": str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )


# @extend_schema(
#     request=EmailTokenObtainPairSerializer,
#     responses={200: EmailTokenObtainPairSerializer},
#     description="Obtain JWT access & refresh tokens",
#     tags=["Authentication"],
# )
# class LoginView(TokenObtainPairView):
#     """
#     POST /auth/login/  { "email": "...", "password": "..." }
#     →  { "refresh": "...", "access": "..." }
#     """

#     permission_classes = (AllowAny,)
#     serializer_class = EmailTokenObtainPairSerializer

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         try:
#             serializer.is_valid(raise_exception=True)
#         except Exception as e:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         # Get user and tokens
#         user = serializer.user
#         tokens = serializer.validated_data

#         # Serialize user data
#         user_data = UserSerializer(user).data

#         return Response(
#             {
#                 "user": user_data,
#                 "tokens": tokens,
#             },
#             status=status.HTTP_200_OK,
#         )


# @extend_schema(
#     request=TokenRefreshRequestSerializer,
#     responses={200: TokenRefreshResponseSerializer},
#     description="Refresh access token",
#     tags=["Authentication"],
# )
# class RefreshView(TokenRefreshView):
#     """
#     POST /auth/refresh/ { "refresh": "..." }
#     → { "access": "..." }
#     """

#     permission_classes = (AllowAny,)


# @extend_schema(
#     request=LogoutRequestSerializer,
#     responses={205: OpenApiResponse(description="Refresh token blacklisted")},
#     description="Logout and blacklist the provided refresh token",
#     tags=["Authentication"],
# )
# class LogoutView(GenericAPIView):
#     """
#     POST /auth/logout/ { "refresh": "..." }
#     → 204 No Content (blacklists the refresh token)
#     """

#     permission_classes = (IsAuthenticated,)
#     serializer_class = LogoutRequestSerializer


#     def post(self, request):
#         try:
#             refresh_token = request.data["refresh"]
#             token = RefreshToken(refresh_token)
#             token.blacklist()
#             return Response(status=status.HTTP_205_RESET_CONTENT)
#         except KeyError:
#             return Response(
#                 {"detail": "`refresh` field is required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         except (TokenError, InvalidToken) as e:
#             return Response(
#                 {"detail": "Invalid token", "error": str(e)},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         except Exception as e:
#             return Response(
#                 {"detail": "Logout failed", "error": str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )
@extend_schema(
    request=RegisterSerializer,
    responses={201: RegisterSerializer},
    description="Register a new user; returns JWT tokens and sets session cookie",
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

            # Generate JWT tokens for the new user
            refresh = RefreshToken.for_user(user)
            tokens = {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }

            # Log in user (creates session)
            login(request, user)

            # Serialize user data
            user_data = UserSerializer(user).data

            return Response(
                {
                    "user": user_data,
                    "tokens": tokens,
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


@extend_schema(
    request=EmailTokenObtainPairSerializer,
    responses={200: EmailTokenObtainPairSerializer},
    description="Obtain JWT access & refresh tokens and set session cookie",
    tags=["Authentication"],
)
class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            tokens = serializer.validated_data

            # Log in user (creates session)
            login(request, user)

            # Serialize user data
            user_data = UserSerializer(user).data

            return Response(
                {
                    "user": user_data,
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )
        except serializers.ValidationError as ve:
            return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Login failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Token Refresh ──────────────────────────────────────────────────────────


@extend_schema(
    request=TokenRefreshRequestSerializer,
    responses={200: TokenRefreshResponseSerializer},
    description="Refresh access token",
    tags=["Authentication"],
)
class RefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)


# ─── Logout ─────────────────────────────────────────────────────────────────


@extend_schema(
    request=LogoutRequestSerializer,
    responses={
        205: OpenApiResponse(description="Refresh token blacklisted, session cleared")
    },
    description="Logout and blacklist the provided refresh token and clear session",
    tags=["Authentication"],
)
class LogoutView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LogoutRequestSerializer

    def post(self, request):
        try:
            # Blacklist JWT refresh token if present
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

            # Log out user from session
            try:
                logout(request)
            except Exception as e:
                # If session is already logged out, just pass
                pass

            return Response(
                {"detail": "Logged out and token blacklisted (if provided)"},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except KeyError:
            return Response(
                {"detail": "`refresh` field is required"},
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
            response=EventSerializer(many=True),
            description="List all events assigned to a given user",
            tags=["User Assigned Events"],
        )
    }
)
class UserAssignedEventsAPIView(APIView):
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            events = Event.objects.filter(staff_assignments__user=user).distinct()
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
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            sessions = Session.objects.filter(staff_assignments__user=user).distinct()
            return Response(SessionSerializer(sessions, many=True).data)
        except Exception as e:
            return Response(
                {"detail": "Error listing assigned sessions", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
