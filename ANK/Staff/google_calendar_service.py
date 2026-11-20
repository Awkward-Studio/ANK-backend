import base64
import re
from urllib.parse import quote

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException

from Staff.models import GoogleCalendarConnection


EVENT_SCOPE = "https://www.googleapis.com/auth/calendar.events"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{}/events"


class CalendarError(APIException):
    def __init__(self, detail, status_code=503):
        self.status_code = status_code
        super().__init__(detail)


def valid_client_id():
    return re.fullmatch(
        r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com",
        settings.GOOGLE_CALENDAR_CLIENT_ID,
    ) is not None


def configured():
    return valid_client_id() and all((
        settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        settings.GOOGLE_CALENDAR_ACCOUNT_EMAIL,
        settings.GOOGLE_CALENDAR_APP_ORIGIN,
        settings.GOOGLE_CALENDAR_REDIRECT_URI,
        settings.GOOGLE_CALENDAR_ID,
    )) and settings.GOOGLE_CALENDAR_ID.lower() != "primary"


def connection():
    return GoogleCalendarConnection.objects.filter(
        pk=1,
        calendar_id=settings.GOOGLE_CALENDAR_ID,
        client_id=settings.GOOGLE_CALENDAR_CLIENT_ID,
        account_email__iexact=settings.GOOGLE_CALENDAR_ACCOUNT_EMAIL,
    ).first()


def cipher():
    key = salted_hmac("ank.google-calendar.encryption", "", algorithm="sha256").digest()
    return Fernet(base64.urlsafe_b64encode(key))


def google_request(method, url, *, token=None, headers=None, **kwargs):
    headers = dict(headers or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(
            method, url, headers=headers, timeout=(3, 8), allow_redirects=False, **kwargs
        )
    except requests.RequestException:
        raise CalendarError("Google Calendar is unreachable. Try again.") from None

    if response.status_code == 204:
        return {}
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.ok and response.status_code < 300 and isinstance(payload, dict):
        return payload
    if url == TOKEN_URL and isinstance(payload, dict) and payload.get("error") == "invalid_grant":
        raise CalendarError("Google authorization expired or was revoked. Connect again.", 409)
    if response.status_code in (401, 403):
        raise CalendarError("Google denied calendar access. Ask an ANK admin to check the connection.", 424)
    if response.status_code in (404, 410):
        raise CalendarError("The event or calendar is no longer available.", response.status_code)
    if response.status_code in (409, 412):
        raise CalendarError("The event changed in Google Calendar. Refresh and try again.", response.status_code)
    if response.status_code == 400 and token:
        raise CalendarError("Google Calendar rejected the meeting details.", 422)
    raise CalendarError("Google Calendar could not complete the request. Try again.")


def token_request(**grant):
    return google_request("POST", TOKEN_URL, data={
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        **grant,
    })


def access_token(*, notes=False):
    if not configured():
        raise CalendarError("Google Calendar setup is incomplete.")
    saved = connection()
    if not saved:
        raise CalendarError("Ask an ANK admin to connect the team calendar.")
    encrypted = saved.notes_refresh_token if notes else saved.refresh_token
    if notes and not encrypted:
        raise CalendarError("Connect Gemini notes from Team Calendar first.", 409)
    try:
        refresh_token = cipher().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise CalendarError("Ask an ANK admin to reconnect the team calendar.") from None
    tokens = token_request(grant_type="refresh_token", refresh_token=refresh_token)
    token = tokens.get("access_token")
    if not token:
        raise CalendarError("Google Calendar could not refresh access. Try again.")
    return token


def calendar_request(method, token, event_id=None, **kwargs):
    url = EVENTS_URL.format(quote(settings.GOOGLE_CALENDAR_ID, safe=""))
    if event_id:
        url += "/" + quote(event_id, safe="")
    return google_request(method, url, token=token, **kwargs)
