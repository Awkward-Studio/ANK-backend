from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from Staff.google_calendar_service import CalendarError, token_request, valid_client_id
from Staff.models import User
from Staff.views import login_response


CALLBACK_PATH = "/api/auth/google/callback"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
google_keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=5)


def login_enabled():
    return bool(
        settings.USE_JWT
        and valid_client_id()
        and settings.GOOGLE_CALENDAR_CLIENT_SECRET
        and settings.GOOGLE_LOGIN_DOMAIN
        and settings.GOOGLE_CALENDAR_APP_ORIGIN
    )


class StartSerializer(serializers.Serializer):
    state = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z")
    nonce = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z")
    challenge = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z")


class CompleteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=2048, trim_whitespace=False)
    nonce = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z")
    verifier = serializers.RegexField(r"\A[A-Za-z0-9_-]{64}\Z")


def verified_identity(id_token, nonce):
    if not isinstance(id_token, str) or len(id_token) > 8192:
        raise PermissionDenied("Google could not verify your sign-in.")
    try:
        signing_key = google_keys.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token, signing_key.key, algorithms=["RS256"],
            audience=settings.GOOGLE_CALENDAR_CLIENT_ID,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
            leeway=30,
        )
    except jwt.PyJWTError:
        raise PermissionDenied("Google could not verify your sign-in.") from None
    if not constant_time_compare(str(claims["nonce"]), nonce):
        raise PermissionDenied("Google could not verify your sign-in.")
    return claims


def linked_user(claims):
    domain = settings.GOOGLE_LOGIN_DOMAIN
    email = claims.get("email")
    subject = claims.get("sub")
    if (
        claims.get("hd") != domain
        or claims.get("email_verified") is not True
        or not isinstance(email, str)
        or email.lower().rpartition("@")[2] != domain
        or not isinstance(subject, str)
        or not 0 < len(subject) <= 255
    ):
        raise PermissionDenied("Use your ANK Google Workspace account.")

    try:
        with transaction.atomic():
            user = User.objects.select_for_update().get(email__iexact=email, is_active=True)
            if user.google_login_subject and user.google_login_subject != subject:
                raise PermissionDenied("Ask an ANK administrator to check your account link.")
            if not user.google_login_subject:
                user.google_login_subject = subject
                user.save(update_fields=["google_login_subject"])
            return user
    except (User.DoesNotExist, User.MultipleObjectsReturned, IntegrityError):
        raise PermissionDenied("Your Google account must match an active ANK account.") from None


@method_decorator(never_cache, name="dispatch")
class GoogleLoginStartView(GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = "auth"
    serializer_class = StartSerializer

    def get(self, _request):
        return Response({"enabled": login_enabled()})

    def post(self, request):
        if not login_enabled():
            return Response({"detail": "Google login is unavailable."}, status=503)
        form = self.get_serializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        query = urlencode({
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_CALENDAR_APP_ORIGIN + CALLBACK_PATH,
            "response_type": "code",
            "scope": "openid email",
            "prompt": "select_account",
            "hd": settings.GOOGLE_LOGIN_DOMAIN,
            "state": data["state"],
            "nonce": data["nonce"],
            "code_challenge": data["challenge"],
            "code_challenge_method": "S256",
        })
        return Response({
            "authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
        })


@method_decorator(never_cache, name="dispatch")
class GoogleLoginCompleteView(GenericAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = "auth"
    serializer_class = CompleteSerializer

    def post(self, request):
        if not login_enabled():
            return Response({"detail": "Google login is unavailable."}, status=503)
        form = self.get_serializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        try:
            tokens = token_request(
                grant_type="authorization_code",
                code=data["code"],
                code_verifier=data["verifier"],
                redirect_uri=settings.GOOGLE_CALENDAR_APP_ORIGIN + CALLBACK_PATH,
            )
        except CalendarError:
            raise PermissionDenied("Google could not complete sign-in. Try again.") from None
        user = linked_user(verified_identity(tokens.get("id_token"), data["nonce"]))
        return login_response(request, user)
