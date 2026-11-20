import base64
import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from Staff.google_calendar_service import (
    EVENT_SCOPE,
    USERINFO_URL,
    CalendarError,
    access_token,
    calendar_request,
    cipher,
    configured,
    connection,
    google_request,
    token_request,
    valid_client_id,
)
from Staff.models import (
    GoogleCalendarConnection,
    GoogleCalendarMeeting,
    GoogleCalendarOAuthAttempt,
)


ATTEMPT_LIFETIME = timedelta(minutes=10)
ADMIN_ROLES = {"admin", "super_admin"}
SCHEDULER_ROLES = ADMIN_ROLES | {"department_head"}


def is_admin(user):
    return user.is_superuser or user.role in ADMIN_ROLES


def can_schedule(user):
    return user.is_superuser or user.role in SCHEDULER_ROLES


def require_admin(user):
    if not is_admin(user):
        raise PermissionDenied()


def pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def active_attempts():
    return GoogleCalendarOAuthAttempt.objects.filter(
        created_at__gte=timezone.now() - ATTEMPT_LIFETIME
    )


@never_cache
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def google_calendar_connection(request):
    enabled = configured()
    if request.method == "DELETE":
        require_admin(request.user)
        with transaction.atomic():
            GoogleCalendarOAuthAttempt.objects.all().delete()
            GoogleCalendarConnection.objects.filter(pk=1).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    saved = connection() if enabled else None
    return Response({
        "configured": enabled,
        "connected": saved is not None,
        "can_connect": is_admin(request.user),
        "can_schedule": can_schedule(request.user),
        "account_email": saved.account_email if saved and is_admin(request.user) else None,
    })


@never_cache
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def google_calendar_start(request):
    require_admin(request.user)
    if settings.GOOGLE_CALENDAR_CLIENT_ID and not valid_client_id():
        raise CalendarError("The backend Google Calendar client ID is invalid.")
    if not configured():
        raise CalendarError("Google Calendar setup is incomplete.")
    origin = request.headers.get("Origin")
    if origin and origin != settings.GOOGLE_CALENDAR_APP_ORIGIN:
        raise CalendarError("Open Team Calendar on the configured ANK site to connect Google.", 400)
    GoogleCalendarOAuthAttempt.objects.filter(
        created_at__lt=timezone.now() - ATTEMPT_LIFETIME
    ).delete()
    verifier = secrets.token_urlsafe(48)
    attempt = GoogleCalendarOAuthAttempt.objects.create(
        user=request.user,
        state=secrets.token_urlsafe(32),
        challenge=pkce_challenge(verifier),
    )
    query = urlencode({
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_CALENDAR_REDIRECT_URI,
        "response_type": "code",
        "scope": f"openid email {EVENT_SCOPE}",
        "access_type": "offline",
        "prompt": "consent select_account",
        "login_hint": settings.GOOGLE_CALENDAR_ACCOUNT_EMAIL,
        "state": attempt.state,
        "code_challenge": attempt.challenge,
        "code_challenge_method": "S256",
    })
    return Response({
        "authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}",
        "state": attempt.state,
        "verifier": verifier,
    })


@never_cache
@require_GET
def google_calendar_callback(request):
    if not request.GET:
        return JsonResponse(
            {"detail": "Start the Google Calendar connection from ANK."}, status=400
        )
    if not configured():
        return JsonResponse(
            {"detail": "Google Calendar connections are not enabled yet."}, status=503
        )

    state = request.GET.get("state", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
        return JsonResponse({"detail": "Start a new connection from ANK."}, status=400)
    attempts = active_attempts().filter(state=state, authorization_code="", claimed=False)
    code = request.GET.get("code", "")
    if request.GET.get("error") and attempts.exists():
        return HttpResponseRedirect(
            f"{settings.GOOGLE_CALENDAR_APP_ORIGIN}/team-calendar#google=denied"
        )
    if not code or len(code) > 2048 or not attempts.update(
        authorization_code=cipher().encrypt(code.encode()).decode()
    ):
        return JsonResponse({"detail": "Start a new connection from ANK."}, status=400)
    response = HttpResponseRedirect(
        f"{settings.GOOGLE_CALENDAR_APP_ORIGIN}/team-calendar#google={state}"
    )
    response["Referrer-Policy"] = "no-referrer"
    return response


class ConnectSerializer(serializers.Serializer):
    state = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z")
    verifier = serializers.RegexField(r"\A[A-Za-z0-9_-]{64}\Z")


@never_cache
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def google_calendar_complete(request):
    require_admin(request.user)
    if not configured():
        raise CalendarError("Google Calendar setup is incomplete.")
    form = ConnectSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    verifier = form.validated_data["verifier"]
    with transaction.atomic():
        attempt = active_attempts().select_for_update().filter(
            state=form.validated_data["state"], user=request.user
        ).first()
        if not attempt or not attempt.authorization_code or not constant_time_compare(
            attempt.challenge, pkce_challenge(verifier)
        ):
            raise CalendarError("Start a new connection from ANK.", 400)
        encrypted_code = attempt.authorization_code
        # Claim the callback before contacting Google. A second request cannot
        # exchange the same code, and disconnect can still invalidate the claim.
        attempt.authorization_code = ""
        attempt.claimed = True
        attempt.save(update_fields=["authorization_code", "claimed"])

    try:
        code = cipher().decrypt(encrypted_code.encode()).decode()
    except InvalidToken:
        raise CalendarError("Start a new connection from ANK.", 400) from None
    tokens = token_request(
        grant_type="authorization_code",
        code=code,
        code_verifier=verifier,
        redirect_uri=settings.GOOGLE_CALENDAR_REDIRECT_URI,
    )
    refresh, token = tokens.get("refresh_token"), tokens.get("access_token")
    if not refresh or not token or EVENT_SCOPE not in tokens.get("scope", "").split():
        raise CalendarError("Approve calendar access again to finish connecting.", 409)
    identity = google_request("GET", USERINFO_URL, token=token)
    email = identity.get("email", "")
    if not identity.get("email_verified") or email.lower() != settings.GOOGLE_CALENDAR_ACCOUNT_EMAIL.lower():
        raise CalendarError("Connect with the designated Workspace calendar account.", 403)
    calendar = calendar_request("GET", token, params={"maxResults": 1, "fields": "accessRole"})
    if calendar.get("accessRole") not in {"owner", "writer"}:
        raise CalendarError("Give the Google account permission to edit the shared calendar.", 424)
    with transaction.atomic():
        deleted, _ = active_attempts().filter(state=attempt.state, claimed=True).delete()
        if not deleted:
            raise CalendarError("Start a new connection from ANK.", 409)
        GoogleCalendarConnection.objects.update_or_create(
            pk=1,
            defaults={
                "calendar_id": settings.GOOGLE_CALENDAR_ID,
                "account_email": email,
                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                "refresh_token": cipher().encrypt(refresh.encode()).decode(),
            },
        )
    return Response({"connected": True})


class EventWindowSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    page = serializers.CharField(required=False, max_length=2048)

    def validate(self, attrs):
        duration = attrs["end"] - attrs["start"]
        if not timedelta(0) < duration <= timedelta(days=93):
            raise ValidationError("Choose a date range of 93 days or less.")
        return attrs


class MeetingSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=255)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    location = serializers.CharField(required=False, allow_blank=True, max_length=500)
    attendees = serializers.ListField(
        child=serializers.EmailField(), required=False, max_length=100
    )

    def validate(self, attrs):
        if attrs["end"] <= attrs["start"]:
            raise ValidationError("The end time must be after the start time.")
        return attrs


class CreateMeetingSerializer(MeetingSerializer):
    request_id = serializers.UUIDField()


def meeting_payload(data):
    payload = {
        "summary": data["summary"],
        "start": {"dateTime": data["start"].isoformat()},
        "end": {"dateTime": data["end"].isoformat()},
    }
    for field in ("description", "location"):
        if field in data:
            payload[field] = data[field]
    if "attendees" in data:
        emails = dict.fromkeys(email.lower() for email in data["attendees"])
        payload["attendees"] = [{"email": email} for email in emails]
    return payload


def is_ank_event(event, meeting):
    marker = event.get("extendedProperties", {}).get("private", {}).get("ankManaged", "")
    return bool(meeting and constant_time_compare(marker, meeting.marker.hex))


def manageable(event, meeting, user):
    return bool(
        is_ank_event(event, meeting)
        and event.get("organizer", {}).get("self")
        and event.get("eventType", "default") == "default"
        and event.get("start", {}).get("dateTime")
        and not event.get("recurringEventId")
        and not event.get("recurrence")
        and event.get("visibility") not in {"private", "confidential"}
        and (is_admin(user) or meeting.created_by_id == user.pk)
    )


def event_data(event, meeting, user):
    private = event.get("visibility") in {"private", "confidential"}
    can_manage = manageable(event, meeting, user)
    link = event.get("htmlLink", "")
    target = urlsplit(link)
    google_calendar_link = target.hostname == "calendar.google.com" or (
        target.hostname == "www.google.com" and target.path.startswith("/calendar/")
    )
    if target.scheme != "https" or not google_calendar_link:
        link = ""
    return {
        "id": event["id"],
        "summary": "Busy" if private else event.get("summary") or "Untitled meeting",
        "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
        "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
        "all_day": "date" in event.get("start", {}),
        "description": "" if private else event.get("description", ""),
        "location": "" if private else event.get("location", ""),
        "attendees": [] if private else [
            {"email": guest["email"], "response": guest.get("responseStatus")}
            for guest in event.get("attendees", []) if guest.get("email")
        ],
        "html_link": "" if private else link,
        "source": "ank" if is_ank_event(event, meeting) else "google",
        "can_manage": can_manage,
        "etag": event.get("etag") if can_manage else None,
    }


def list_events(request):
    form = EventWindowSerializer(data=request.query_params)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    params = {
        "timeMin": data["start"].isoformat(),
        "timeMax": data["end"].isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 100,
    }
    if data.get("page"):
        params["pageToken"] = data["page"]
    result = calendar_request("GET", access_token(), params=params)
    events = [event for event in result.get("items", []) if event.get("status") != "cancelled"]
    meetings = {
        meeting.event_id: meeting
        for meeting in GoogleCalendarMeeting.objects.filter(
            calendar_id=settings.GOOGLE_CALENDAR_ID,
            event_id__in=[event["id"] for event in events],
        )
    }
    return Response({
        "events": [event_data(event, meetings.get(event["id"]), request.user) for event in events],
        "next_page": result.get("nextPageToken"),
    })


@never_cache
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def google_calendar_events(request):
    if request.method == "GET":
        return list_events(request)
    if not can_schedule(request.user):
        raise PermissionDenied()
    form = CreateMeetingSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    token = access_token()
    event_id = data["request_id"].hex
    meeting, _ = GoogleCalendarMeeting.objects.get_or_create(
        calendar_id=settings.GOOGLE_CALENDAR_ID, event_id=event_id,
        defaults={"created_by": request.user},
    )
    if meeting.created_by_id != request.user.pk:
        raise PermissionDenied()
    try:
        event = calendar_request(
            "POST", token, json={
                "id": event_id,
                "extendedProperties": {"private": {"ankManaged": meeting.marker.hex}},
                **meeting_payload(data),
            },
            params={"sendUpdates": "all"},
        )
    except CalendarError as exc:
        if exc.status_code != 409:
            raise
        event = calendar_request("GET", token, event_id)
        if not is_ank_event(event, meeting) or event.get("status") == "cancelled":
            raise CalendarError("Create a new meeting and try again.", 409) from None
    return Response(event_data(event, meeting, request.user), status=status.HTTP_201_CREATED)


@never_cache
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def google_calendar_event(request, event_id):
    meeting = GoogleCalendarMeeting.objects.filter(
        calendar_id=settings.GOOGLE_CALENDAR_ID, event_id=event_id
    ).first()
    if not meeting or not (is_admin(request.user) or meeting.created_by_id == request.user.pk):
        raise PermissionDenied()
    etag = request.headers.get("If-Match", "")
    if not re.fullmatch(r'"[^"\r\n]{1,128}"', etag):
        raise ValidationError("Refresh the calendar before changing the meeting.")
    form = MeetingSerializer(data=request.data)
    if request.method == "PATCH":
        form.is_valid(raise_exception=True)
    token = access_token()
    existing = calendar_request("GET", token, event_id)
    if not manageable(existing, meeting, request.user):
        raise PermissionDenied()
    if existing.get("etag") != etag:
        raise CalendarError("The event changed in Google Calendar. Refresh and try again.", 412)
    options = {"headers": {"If-Match": etag}, "params": {"sendUpdates": "all"}}
    if request.method == "DELETE":
        calendar_request("DELETE", token, event_id, **options)
        return Response(status=status.HTTP_204_NO_CONTENT)
    data = meeting_payload(form.validated_data)
    if "attendees" in data:
        previous = {
            guest["email"].lower(): guest
            for guest in existing.get("attendees", []) if guest.get("email")
        }
        for guest in data["attendees"]:
            response = previous.get(guest["email"], {}).get("responseStatus")
            if response:
                guest["responseStatus"] = response
    result = calendar_request("PATCH", token, event_id, json=data, **options)
    return Response(event_data(result, meeting, request.user))
