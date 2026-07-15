import logging
import os
from typing import Dict, Iterable, List, Tuple

import requests
from django.utils import timezone

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
# Align template capability checks with the Communications template manager.
TEMPLATE_GRAPH_API_BASE = "https://graph.facebook.com/v20.0"

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


def _get_waba_token(waba: WhatsAppBusinessAccount) -> str:
    token = waba.get_token()
    if token:
        return token

    phone = waba.phone_numbers.first()
    if phone:
        token = phone.get_access_token(allow_env_fallback=False)
        if token:
            return token

    return os.getenv("WABA_ACCESS_TOKEN", "")


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


def reconcile_waba_phone_numbers(waba: WhatsAppBusinessAccount) -> Dict[str, object]:
    """
    Compare local phone numbers for one WABA with Meta's current phone list.
    Missing numbers are treated as logged_out because embedded signup numbers can
    disappear from a WABA after Meta/business-side changes.
    """
    local_numbers = list(waba.phone_numbers.all())
    meta_numbers, fetch_error, fetch_status = _fetch_waba_phone_numbers(waba)
    template_management = _template_management_capability(waba)
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
            phone.platform_type = meta_phone.get("platform_type") or ""

        phone.meta_last_checked_at = checked_at
        phone.save(
            update_fields=[
                "display_phone_number",
                "verified_name",
                "quality_rating",
                "messaging_limit_tier",
                "platform_type",
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
    }


def reconcile_all_wabas(wabas: Iterable[WhatsAppBusinessAccount] = None) -> List[Dict[str, object]]:
    queryset = wabas if wabas is not None else WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").all()
    return [reconcile_waba_phone_numbers(waba) for waba in queryset]
