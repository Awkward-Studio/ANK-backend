import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Tuple

import requests
from django.db import close_old_connections
from django.utils import timezone

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
TEMPLATE_GRAPH_API_BASE = GRAPH_API_BASE

PHONE_NUMBER_FIELDS = ",".join(
    [
        "id",
        "display_phone_number",
        "verified_name",
        "quality_rating",
        "messaging_limit_tier",
        "code_verification_status",
        "account_mode",
        "platform_type",
        "name_status",
        "new_name",
        "new_name_status",
        "is_official_business_account",
    ]
)

WABA_AUDIT_FIELDS = [
    "name",
    "owner_business_info",
    "account_review_status",
    "whatsapp_business_manager_messaging_limit",
]


def _meta_error(response, payload: dict) -> dict:
    error = payload.get("error") or {}
    return {
        "message": error.get("error_user_msg") or error.get("message") or response.text[:300],
        "code": error.get("code"),
        "subcode": error.get("error_subcode"),
        "trace_id": error.get("fbtrace_id"),
        "http_status": response.status_code,
    }


def _meta_get(path: str, access_token: str, params=None) -> Tuple[dict, dict]:
    try:
        response = requests.get(
            f"{GRAPH_API_BASE}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=10,
        )
    except requests.RequestException as exc:
        return {}, {"message": str(exc), "http_status": None}

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.ok:
        return payload, {}
    return {}, _meta_error(response, payload)


def _get_app_credentials() -> Tuple[str, str]:
    app_id = os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID") or ""
    app_token = os.getenv("META_APP_ACCESS_TOKEN") or os.getenv("FACEBOOK_APP_ACCESS_TOKEN") or ""
    if app_token:
        return app_id, app_token

    app_secret = os.getenv("META_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET") or ""
    if app_id and app_secret:
        return app_id, f"{app_id}|{app_secret}"
    return app_id, ""


def _template_management_capability(waba: WhatsAppBusinessAccount) -> Dict[str, str]:
    """Check whether the saved token can access this WABA's template edge.

    Meta creates templates at the WABA level, rather than against an individual
    phone number.  A successful read proves management-edge access but does not
    submit a template or guarantee approval, policy eligibility, or quota.
    """
    token = _get_waba_token(waba)
    if not token:
        return {
            "status": "unavailable",
            "reason": "No access token available for this WABA",
        }

    try:
        response = requests.get(
            f"{TEMPLATE_GRAPH_API_BASE}/{waba.waba_id}/message_templates",
            params={"access_token": token, "fields": "name", "limit": 1},
            timeout=10,
        )
        if response.ok:
            return {"status": "available", "reason": ""}

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error") or {}
        message = error.get("message") or response.text[:300]
        code = error.get("code")
        lowered = str(message).lower()
        if (
            response.status_code in {400, 401, 403, 404}
            or code in {10, 100, 190, 200}
            or "unsupported get request" in lowered
            or "permission" in lowered
            or "access token" in lowered
        ):
            return {"status": "unavailable", "reason": message}
        return {"status": "unknown", "reason": message}
    except requests.RequestException as error:
        return {"status": "unknown", "reason": str(error)}


def _get_waba_token_with_source(waba: WhatsAppBusinessAccount) -> Tuple[str, str]:
    token = waba.get_token()
    if token:
        return token, "encrypted_waba_token"

    phone = waba.phone_numbers.first()
    if phone:
        token = phone.get_access_token(allow_env_fallback=False)
        if token:
            return token, "encrypted_phone_token"

    token = os.getenv("WABA_ACCESS_TOKEN", "")
    return (token, "production_environment") if token else ("", "missing")


def _get_waba_token(waba: WhatsAppBusinessAccount) -> str:
    token, _source = _get_waba_token_with_source(waba)
    return token


def _fetch_fields_with_fallback(object_id: str, fields: List[str], token: str) -> Tuple[dict, dict]:
    values = {"id": object_id}
    errors = {}
    with ThreadPoolExecutor(max_workers=len(fields)) as executor:
        results = executor.map(
            lambda field: (field, *_meta_get(object_id, token, {"fields": field})),
            fields,
        )
    for field, field_payload, field_error in results:
        if field_error:
            errors[field] = field_error
        elif field in field_payload:
            values[field] = field_payload[field]
    return values, errors


def _token_audit(token: str, waba_id: str) -> dict:
    expected_app_id, app_token = _get_app_credentials()
    result = {
        "status": "unknown",
        "introspection_credential_source": "app_token" if app_token else "waba_token_fallback",
        "is_valid": None,
        "app_id": None,
        "expected_app_id": expected_app_id or None,
        "app_matches": None,
        "expires_at": None,
        "data_access_expires_at": None,
        "scopes": [],
        "required_scopes_granted": None,
        "waba_in_granular_targets": None,
        "error": None,
    }
    payload, error = _meta_get("debug_token", app_token or token, {"input_token": token})
    if error:
        result.update({"status": "error", "error": error})
        return result

    data = payload.get("data") or {}
    granular_scopes = data.get("granular_scopes") or []
    scopes = sorted(
        set(data.get("scopes") or [])
        | {str(scope.get("scope")) for scope in granular_scopes if scope.get("scope")}
    )
    required = {"whatsapp_business_management", "whatsapp_business_messaging"}
    target_ids = {
        str(target_id)
        for scope in granular_scopes
        for target_id in scope.get("target_ids") or []
    }
    token_app_id = str(data.get("app_id") or "")
    result.update(
        {
            "status": "valid" if data.get("is_valid") else "invalid",
            "is_valid": bool(data.get("is_valid")),
            "app_id": token_app_id or None,
            "app_matches": token_app_id == expected_app_id if expected_app_id else None,
            "expires_at": data.get("expires_at") or None,
            "data_access_expires_at": data.get("data_access_expires_at") or None,
            "scopes": scopes,
            "required_scopes_granted": required.issubset(set(scopes)),
            "waba_in_granular_targets": str(waba_id) in target_ids if target_ids else None,
            "error": None,
        }
    )
    return result


def _subscription_audit(waba_id: str, token: str, expected_app_id: str = "") -> dict:
    configured_app_id, _app_token = _get_app_credentials()
    expected_app_id = expected_app_id or configured_app_id
    payload, error = _meta_get(
        f"{waba_id}/subscribed_apps",
        token,
        {"limit": 100},
    )
    if error:
        return {
            "status": "error",
            "subscribed": None,
            "expected_app_id": expected_app_id or None,
            "apps": [],
            "error": error,
        }

    apps = []
    for row in payload.get("data") or []:
        app = row.get("whatsapp_business_api_data") or row
        if app.get("id"):
            apps.append({"id": str(app.get("id")), "name": app.get("name")})
    subscribed = (
        any(app["id"] == expected_app_id for app in apps)
        if expected_app_id
        else None
    )
    return {
        "status": "verified" if subscribed else ("app_id_not_configured" if subscribed is None else "not_subscribed"),
        "subscribed": subscribed,
        "expected_app_id": expected_app_id or None,
        "apps": apps,
        "error": None,
    }


def build_waba_verification(waba: WhatsAppBusinessAccount) -> dict:
    token, token_source = _get_waba_token_with_source(waba)
    checked_at = timezone.now().isoformat()
    if not token:
        return {
            "graph_api_version": GRAPH_API_VERSION,
            "checked_at": checked_at,
            "token_source": token_source,
            "token": {"status": "missing", "is_valid": None, "error": "No server-side WABA token is configured."},
            "waba": {"id": str(waba.waba_id), "fields": {}, "field_errors": {}},
            "app_subscription": {"status": "unknown", "subscribed": None, "apps": [], "error": "No token available."},
        }

    configured_app_id, _app_token = _get_app_credentials()
    with ThreadPoolExecutor(max_workers=3) as executor:
        fields_future = executor.submit(
            _fetch_fields_with_fallback,
            str(waba.waba_id),
            WABA_AUDIT_FIELDS,
            token,
        )
        token_future = executor.submit(_token_audit, token, str(waba.waba_id))
        subscription_future = executor.submit(
            _subscription_audit,
            str(waba.waba_id),
            token,
            configured_app_id,
        )
        waba_fields, field_errors = fields_future.result()
        token_audit = token_future.result()
        subscription_audit = subscription_future.result()

    if subscription_audit.get("subscribed") is None and token_audit.get("app_id"):
        expected_app_id = str(token_audit["app_id"])
        subscription_audit["expected_app_id"] = expected_app_id
        subscription_audit["subscribed"] = any(
            app.get("id") == expected_app_id for app in subscription_audit.get("apps") or []
        )
        subscription_audit["status"] = (
            "verified" if subscription_audit["subscribed"] else "not_subscribed"
        )
    return {
        "graph_api_version": GRAPH_API_VERSION,
        "checked_at": checked_at,
        "token_source": token_source,
        "token": token_audit,
        "waba": {
            "id": str(waba.waba_id),
            "fields": waba_fields,
            "field_errors": field_errors,
        },
        "app_subscription": subscription_audit,
    }


def _fetch_waba_phone_numbers(waba: WhatsAppBusinessAccount) -> Tuple[List[dict], str, str]:
    token = _get_waba_token(waba)
    if not token:
        return [], "No access token available for this WABA", "logged_out"

    url = f"{GRAPH_API_BASE}/{waba.waba_id}/phone_numbers"
    params = {"fields": PHONE_NUMBER_FIELDS, "limit": 100}
    numbers: List[dict] = []

    while url:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        params = None

        try:
            payload = response.json()
        except ValueError:
            return [], f"Meta returned non-JSON response ({response.status_code})", "unknown"

        if not response.ok:
            error = payload.get("error") or {}
            message = error.get("message") or response.text[:300]
            code = error.get("code")
            error_subcode = error.get("error_subcode")
            lowered = str(message).lower()
            if (
                response.status_code in {400, 401, 403}
                or code in {10, 100, 190, 200}
                or error_subcode in {33, 2018001}
                or "unsupported get request" in lowered
                or "does not exist" in lowered
                or "object with id" in lowered
                or "permission" in lowered
                or "access token" in lowered
            ):
                return [], message, "logged_out"
            return [], message, "unknown"

        numbers.extend(payload.get("data") or [])
        url = (payload.get("paging") or {}).get("next")

    for number in numbers:
        phone_id = number.get("id")
        if not phone_id:
            continue
        coexistence_payload, coexistence_error = _meta_get(
            str(phone_id), token, {"fields": "is_on_biz_app"}
        )
        if coexistence_error:
            number["is_on_biz_app_error"] = coexistence_error
        elif "is_on_biz_app" in coexistence_payload:
            number["is_on_biz_app"] = coexistence_payload["is_on_biz_app"]

    return numbers, "", ""


def _status_from_meta(meta_phone: dict) -> Tuple[str, str]:
    status_values = {
        str(meta_phone.get("name_status") or "").upper(),
        str(meta_phone.get("new_name_status") or "").upper(),
        str(meta_phone.get("code_verification_status") or "").upper(),
    }
    quality = str(meta_phone.get("quality_rating") or "").upper()

    blocked_markers = {
        "BLOCKED",
        "DISABLED",
        "BANNED",
        "REJECTED",
        "FLAGGED",
        "SUSPENDED",
        "LIMITED",
    }
    if status_values & blocked_markers or quality == "RED":
        reason_parts = [
            f"name_status={meta_phone.get('name_status')}" if meta_phone.get("name_status") else "",
            f"new_name_status={meta_phone.get('new_name_status')}"
            if meta_phone.get("new_name_status")
            else "",
            f"code_verification_status={meta_phone.get('code_verification_status')}"
            if meta_phone.get("code_verification_status")
            else "",
            f"quality_rating={quality}" if quality else "",
        ]
        return "blocked", ", ".join(part for part in reason_parts if part)

    return "active", ""


def phone_identity_verification(meta_phone: dict) -> dict:
    name_status = str(meta_phone.get("name_status") or "UNKNOWN").upper()
    new_name_status = str(meta_phone.get("new_name_status") or "UNKNOWN").upper()
    platform_type = str(meta_phone.get("platform_type") or "UNKNOWN").upper()
    is_on_biz_app = meta_phone.get("is_on_biz_app")
    display_name_approved = name_status == "APPROVED"
    coexistence_confirmed = is_on_biz_app is True and platform_type == "CLOUD_API"
    if coexistence_confirmed:
        coexistence_reason = "Meta reports is_on_biz_app=true and platform_type=CLOUD_API."
    elif meta_phone.get("is_on_biz_app_error"):
        coexistence_reason = "Meta did not allow ANK to read is_on_biz_app with the current token."
    elif is_on_biz_app is False:
        coexistence_reason = "Meta reports is_on_biz_app=false."
    else:
        coexistence_reason = "Meta did not return is_on_biz_app, so coexistence cannot be confirmed."

    if display_name_approved:
        display_name_reason = "Meta reports name_status=APPROVED."
    elif name_status in {"NON_EXISTS", "NONE", "UNKNOWN", ""}:
        display_name_reason = "Meta has not reported an approved display-name review for this number."
    elif name_status in {"PENDING_REVIEW", "PENDING"}:
        display_name_reason = "Meta is reviewing the display name."
    else:
        display_name_reason = f"Meta reports name_status={name_status}."

    return {
        "display_name_approved": display_name_approved,
        "display_name_status": name_status,
        "display_name_reason": display_name_reason,
        "new_name_status": new_name_status,
        "verified_name": meta_phone.get("verified_name"),
        "code_verification_status": meta_phone.get("code_verification_status"),
        "coexistence_confirmed": coexistence_confirmed,
        "coexistence_reason": coexistence_reason,
        "is_on_biz_app": is_on_biz_app,
        "platform_type": platform_type,
        "is_official_business_account": meta_phone.get("is_official_business_account"),
    }


def reconcile_waba_phone_numbers(waba: WhatsAppBusinessAccount) -> Dict[str, object]:
    """
    Compare local phone numbers for one WABA with Meta's current phone list.
    Missing numbers are treated as logged_out because embedded signup numbers can
    disappear from a WABA after Meta/business-side changes.
    """
    local_numbers = list(waba.phone_numbers.all())
    with ThreadPoolExecutor(max_workers=3) as executor:
        numbers_future = executor.submit(_fetch_waba_phone_numbers, waba)
        template_future = executor.submit(_template_management_capability, waba)
        verification_future = executor.submit(build_waba_verification, waba)
        meta_numbers, fetch_error, fetch_status = numbers_future.result()
        template_management = template_future.result()
        waba_verification = verification_future.result()
    checked_at = timezone.now()

    if fetch_error:
        logger.warning("[META-RECONCILE] WABA %s fetch failed: %s", waba.waba_id, fetch_error)
        for phone in local_numbers:
            phone.meta_status = fetch_status or "unknown"
            phone.meta_status_reason = fetch_error
            phone.meta_last_checked_at = checked_at
            phone.save(update_fields=["meta_status", "meta_status_reason", "meta_last_checked_at"])
        return {
            "waba_id": waba.waba_id,
            "fetch_error": fetch_error,
            "numbers": local_numbers,
            "meta_phone_number_ids": [],
            "meta_details_by_phone_id": {},
            "template_management": template_management,
            "verification": waba_verification,
        }

    meta_by_id = {str(item.get("id")): item for item in meta_numbers if item.get("id")}
    meta_ids = set(meta_by_id.keys())

    for phone in local_numbers:
        meta_phone = meta_by_id.get(str(phone.phone_number_id))
        if not meta_phone:
            phone.meta_status = "logged_out"
            phone.meta_status_reason = "Phone number is saved locally but no longer appears under this WABA in Meta"
        else:
            phone.meta_status, phone.meta_status_reason = _status_from_meta(meta_phone)
            phone.display_phone_number = meta_phone.get("display_phone_number") or phone.display_phone_number
            phone.verified_name = meta_phone.get("verified_name") or phone.verified_name
            phone.quality_rating = meta_phone.get("quality_rating") or phone.quality_rating
            phone.messaging_limit_tier = meta_phone.get("messaging_limit_tier") or phone.messaging_limit_tier
            phone.code_verification_status = meta_phone.get("code_verification_status") or ""
            phone.name_status = meta_phone.get("name_status") or ""
            phone.new_name_status = meta_phone.get("new_name_status") or ""
            phone.account_mode = meta_phone.get("account_mode") or ""
            phone.platform_type = meta_phone.get("platform_type") or ""
            phone.is_official_business_account = meta_phone.get("is_official_business_account")

        phone.meta_last_checked_at = checked_at
        phone.save(
            update_fields=[
                "display_phone_number",
                "verified_name",
                "quality_rating",
                "messaging_limit_tier",
                "code_verification_status",
                "name_status",
                "new_name_status",
                "account_mode",
                "platform_type",
                "is_official_business_account",
                "meta_status",
                "meta_status_reason",
                "meta_last_checked_at",
                "updated_at",
            ]
        )

    return {
        "waba_id": waba.waba_id,
        "fetch_error": "",
        "numbers": local_numbers,
        "meta_phone_number_ids": sorted(meta_ids),
        # This is intentionally response-only.  It exposes the complete
        # non-sensitive Meta record for the status UI without persisting an
        # unbounded vendor payload in ANK's database.
        "meta_details_by_phone_id": meta_by_id,
        "template_management": template_management,
        "verification": waba_verification,
    }


def reconcile_all_wabas(wabas: Iterable[WhatsAppBusinessAccount] = None) -> List[Dict[str, object]]:
    queryset = wabas if wabas is not None else WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").all()
    waba_ids = [str(waba.waba_id) for waba in queryset]
    if len(waba_ids) <= 1:
        return [reconcile_waba_phone_numbers(waba) for waba in queryset]

    def reconcile_by_id(waba_id: str) -> Dict[str, object]:
        close_old_connections()
        try:
            waba = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").get(
                waba_id=waba_id
            )
            return reconcile_waba_phone_numbers(waba)
        finally:
            close_old_connections()

    max_workers = min(8, len(waba_ids))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(reconcile_by_id, waba_ids))
