import logging
import os
from typing import Dict, Iterable, List

from django.utils import timezone

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber
from MessageTemplates.services.meta_graph import (
    MetaAuthenticationError,
    MetaGraphClient,
    MetaGraphError,
    MetaNotFoundError,
    MetaPermissionError,
    MetaValidationError,
)

logger = logging.getLogger(__name__)

CORE_DETAIL_FIELDS = [
    "id",
    "display_phone_number",
    "verified_name",
    "quality_rating",
    "code_verification_status",
]
OPTIONAL_DETAIL_FIELDS = [
    "name_status",
    "new_name_status",
    "account_mode",
    "messaging_limit_tier",
    "is_official_business_account",
]


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


def _error_values(error: MetaGraphError) -> tuple[str, str]:
    code = str(error.code or error.status_code or "meta_error")
    return code, str(error)[:1000]


def _access_state(error: MetaGraphError) -> str:
    if isinstance(error, MetaAuthenticationError):
        return "token_expired"
    if isinstance(error, (MetaPermissionError, MetaNotFoundError)):
        return "access_denied"
    return "error"


def _fetch_phone_details(client: MetaGraphClient, list_item: dict) -> tuple[dict, List[str]]:
    """Fetch details without allowing optional/beta fields to break core data."""
    phone_id = str(list_item["id"])
    unavailable: List[str] = []
    details = dict(list_item)
    try:
        details.update(
            client.get_phone_number(
                phone_id, [*CORE_DETAIL_FIELDS, *OPTIONAL_DETAIL_FIELDS]
            )
        )
        return details, unavailable
    except MetaValidationError:
        # Meta rejects the complete request if any optional field is unavailable.
        details.update(client.get_phone_number(phone_id, CORE_DETAIL_FIELDS))

    for field in OPTIONAL_DETAIL_FIELDS:
        try:
            details.update(client.get_phone_number(phone_id, [field]))
        except (MetaValidationError, MetaPermissionError, MetaNotFoundError):
            unavailable.append(field)
    return details, unavailable


def _template_management_capability(
    waba: WhatsAppBusinessAccount, client: MetaGraphClient, checked_at
) -> Dict[str, str]:
    try:
        client.list_templates(waba.waba_id, fields="id,name")
        status, reason = "available", ""
    except (MetaAuthenticationError, MetaPermissionError, MetaNotFoundError) as error:
        status, reason = "denied", str(error)[:1000]
    except MetaGraphError as error:
        status, reason = "error", str(error)[:1000]

    waba.template_access_status = status
    waba.template_access_reason = reason
    waba.template_access_last_checked_at = checked_at
    waba.save(
        update_fields=[
            "template_access_status",
            "template_access_reason",
            "template_access_last_checked_at",
            "updated_at",
        ]
    )
    return {"status": status, "reason": reason, "last_checked_at": checked_at}


def _phone_snapshot(phone: WhatsAppPhoneNumber, details: dict, unavailable: List[str], checked_at):
    snapshot = dict(details)
    snapshot["unavailable_fields"] = unavailable
    phone.meta_details_snapshot = snapshot
    phone.meta_seen_in_waba = True
    phone.meta_access_state = "partial" if unavailable else "reachable"
    phone.meta_last_attempt_at = checked_at
    phone.meta_last_success_at = checked_at
    phone.meta_last_checked_at = checked_at
    phone.meta_fetch_error_code = ""
    phone.meta_fetch_error_message = ""

    # Legacy compatibility only. This is ANK reachability, not a raw Meta status.
    phone.meta_status = "active"
    phone.meta_status_reason = ""

    for field in (
        "display_phone_number",
        "verified_name",
        "quality_rating",
        "messaging_limit_tier",
        "code_verification_status",
        "name_status",
        "new_name_status",
        "account_mode",
    ):
        value = details.get(field)
        if value is not None:
            setattr(phone, field, value)
    if "is_official_business_account" in details:
        phone.is_official_business_account = details.get("is_official_business_account")

    phone.save()


def reconcile_waba_phone_numbers(waba: WhatsAppBusinessAccount) -> Dict[str, object]:
    local_numbers = list(waba.phone_numbers.all())
    checked_at = timezone.now()
    waba.meta_last_attempt_at = checked_at
    token = _get_waba_token(waba)

    if not token:
        error = MetaAuthenticationError("No access token available for this WABA")
        return _record_waba_error(waba, local_numbers, error, checked_at)

    client = MetaGraphClient(token)
    try:
        list_items = client.list_phone_numbers(waba.waba_id)
    except MetaGraphError as error:
        return _record_waba_error(waba, local_numbers, error, checked_at)

    waba.meta_last_success_at = checked_at
    waba.meta_fetch_error_code = ""
    waba.meta_fetch_error_message = ""
    waba.save(
        update_fields=[
            "meta_last_attempt_at",
            "meta_last_success_at",
            "meta_fetch_error_code",
            "meta_fetch_error_message",
            "updated_at",
        ]
    )
    template_management = _template_management_capability(waba, client, checked_at)
    meta_by_id = {str(item["id"]): item for item in list_items if item.get("id")}

    for phone in local_numbers:
        list_item = meta_by_id.get(str(phone.phone_number_id))
        phone.meta_last_attempt_at = checked_at
        phone.meta_last_checked_at = checked_at
        if not list_item:
            phone.meta_seen_in_waba = False
            phone.meta_access_state = "not_in_waba"
            phone.meta_fetch_error_code = "not_in_waba"
            phone.meta_fetch_error_message = (
                "Phone number is saved in ANK but was not returned by this WABA"
            )
            phone.meta_status = "logged_out"
            phone.meta_status_reason = phone.meta_fetch_error_message
            phone.save(
                update_fields=[
                    "meta_seen_in_waba",
                    "meta_access_state",
                    "meta_last_attempt_at",
                    "meta_last_checked_at",
                    "meta_fetch_error_code",
                    "meta_fetch_error_message",
                    "meta_status",
                    "meta_status_reason",
                ]
            )
            continue
        try:
            details, unavailable = _fetch_phone_details(client, list_item)
            meta_by_id[str(phone.phone_number_id)] = details
            _phone_snapshot(phone, details, unavailable, checked_at)
        except MetaGraphError as error:
            code, message = _error_values(error)
            phone.meta_seen_in_waba = True
            phone.meta_access_state = "partial"
            phone.meta_fetch_error_code = code
            phone.meta_fetch_error_message = message
            phone.save(
                update_fields=[
                    "meta_seen_in_waba",
                    "meta_access_state",
                    "meta_last_attempt_at",
                    "meta_last_checked_at",
                    "meta_fetch_error_code",
                    "meta_fetch_error_message",
                ]
            )

    return {
        "waba_id": waba.waba_id,
        "fetch_error": "",
        "numbers": local_numbers,
        "meta_phone_number_ids": sorted(meta_by_id),
        "meta_details_by_phone_id": meta_by_id,
        "template_management": template_management,
    }


def _record_waba_error(waba, local_numbers, error: MetaGraphError, checked_at):
    code, message = _error_values(error)
    state = _access_state(error)
    waba.meta_fetch_error_code = code
    waba.meta_fetch_error_message = message
    waba.save(
        update_fields=[
            "meta_last_attempt_at",
            "meta_fetch_error_code",
            "meta_fetch_error_message",
            "updated_at",
        ]
    )
    logger.warning("[META-RECONCILE] WABA %s: %s", waba.waba_id, message)
    for phone in local_numbers:
        phone.meta_access_state = state
        phone.meta_seen_in_waba = None
        phone.meta_last_attempt_at = checked_at
        phone.meta_last_checked_at = checked_at
        phone.meta_fetch_error_code = code
        phone.meta_fetch_error_message = message
        phone.meta_status = "unknown"
        phone.meta_status_reason = message
        phone.save(
            update_fields=[
                "meta_access_state",
                "meta_seen_in_waba",
                "meta_last_attempt_at",
                "meta_last_checked_at",
                "meta_fetch_error_code",
                "meta_fetch_error_message",
                "meta_status",
                "meta_status_reason",
            ]
        )
    return {
        "waba_id": waba.waba_id,
        "fetch_error": message,
        "numbers": local_numbers,
        "meta_phone_number_ids": [],
        "meta_details_by_phone_id": {
            str(phone.phone_number_id): phone.meta_details_snapshot
            for phone in local_numbers
            if phone.meta_details_snapshot
        },
        "template_management": {
            "status": waba.template_access_status,
            "reason": waba.template_access_reason,
            "last_checked_at": waba.template_access_last_checked_at,
        },
    }


def reconcile_all_wabas(
    wabas: Iterable[WhatsAppBusinessAccount] = None,
) -> List[Dict[str, object]]:
    queryset = wabas if wabas is not None else WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").all()
    return [reconcile_waba_phone_numbers(waba) for waba in queryset]
