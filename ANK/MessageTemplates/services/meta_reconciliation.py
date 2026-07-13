import logging
import os
from typing import Dict, Iterable, List, Tuple

import requests
from django.utils import timezone

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber

logger = logging.getLogger(__name__)

GRAPH_API_BASE = os.getenv("WABA_API_BASE", "https://graph.facebook.com/v21.0")

PHONE_NUMBER_FIELDS = ",".join(
    [
        "id",
        "display_phone_number",
        "verified_name",
        "quality_rating",
        "messaging_limit_tier",
        "code_verification_status",
    ]
)


def _get_waba_token(waba: WhatsAppBusinessAccount) -> str:
    token = waba.get_token()
    if token:
        return token

    phone = waba.phone_numbers.first()
    if phone:
        token = phone.get_access_token()
        if token:
            return token

    return os.getenv("WABA_ACCESS_TOKEN", "")


def _fetch_waba_phone_numbers(waba: WhatsAppBusinessAccount) -> Tuple[List[dict], str]:
    token = _get_waba_token(waba)
    if not token:
        return [], "No access token available for this WABA"

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
            return [], f"Meta returned non-JSON response ({response.status_code})"

        if not response.ok:
            error = payload.get("error") or {}
            message = error.get("message") or response.text[:300]
            return [], message

        numbers.extend(payload.get("data") or [])
        url = (payload.get("paging") or {}).get("next")

    return numbers, ""


def _status_from_meta(meta_phone: dict) -> Tuple[str, str]:
    status_values = {
        str(meta_phone.get("status") or "").upper(),
        str(meta_phone.get("name_status") or "").upper(),
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
            f"status={meta_phone.get('status')}" if meta_phone.get("status") else "",
            f"name_status={meta_phone.get('name_status')}" if meta_phone.get("name_status") else "",
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
    meta_numbers, fetch_error = _fetch_waba_phone_numbers(waba)
    checked_at = timezone.now()

    if fetch_error:
        logger.warning("[META-RECONCILE] WABA %s fetch failed: %s", waba.waba_id, fetch_error)
        for phone in local_numbers:
            phone.meta_status = "unknown"
            phone.meta_status_reason = fetch_error
            phone.meta_last_checked_at = checked_at
            phone.save(update_fields=["meta_status", "meta_status_reason", "meta_last_checked_at"])
        return {
            "waba_id": waba.waba_id,
            "fetch_error": fetch_error,
            "numbers": local_numbers,
            "meta_phone_number_ids": [],
        }

    meta_by_id = {str(item.get("id")): item for item in meta_numbers if item.get("id")}
    meta_ids = set(meta_by_id.keys())

    for phone in local_numbers:
        meta_phone = meta_by_id.get(str(phone.phone_number_id))
        if not meta_phone:
            phone.meta_status = "logged_out"
            phone.meta_status_reason = "Phone number is saved locally but no longer appears under this WABA in Meta"
            phone.is_active = False
        else:
            phone.meta_status, phone.meta_status_reason = _status_from_meta(meta_phone)
            phone.is_active = phone.meta_status == "active"
            phone.display_phone_number = meta_phone.get("display_phone_number") or phone.display_phone_number
            phone.verified_name = meta_phone.get("verified_name") or phone.verified_name
            phone.quality_rating = meta_phone.get("quality_rating") or phone.quality_rating
            phone.messaging_limit_tier = meta_phone.get("messaging_limit_tier") or phone.messaging_limit_tier

        phone.meta_last_checked_at = checked_at
        phone.save(
            update_fields=[
                "display_phone_number",
                "verified_name",
                "quality_rating",
                "messaging_limit_tier",
                "is_active",
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
    }


def reconcile_all_wabas(wabas: Iterable[WhatsAppBusinessAccount] = None) -> List[Dict[str, object]]:
    queryset = wabas if wabas is not None else WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").all()
    return [reconcile_waba_phone_numbers(waba) for waba in queryset]
