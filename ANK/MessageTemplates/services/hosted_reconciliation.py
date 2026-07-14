import hashlib
import json
from collections import Counter
from typing import Iterable

import requests
from django.db import transaction
from django.utils import timezone

from MessageTemplates.models import WhatsAppBusinessAccount, WhatsAppPhoneNumber

GRAPH_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
CORE_FIELDS = ["id", "display_phone_number", "verified_name", "quality_rating"]
DETAIL_FIELDS = [
    "code_verification_status",
    "name_status",
    "new_name_status",
    "account_mode",
    "platform_type",
    "messaging_limit_tier",
    "is_official_business_account",
]
COMPARE_FIELDS = [
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
]
NULLABLE_DETAIL_FIELDS = {"is_official_business_account"}
BLANKABLE_DETAIL_FIELDS = {
    "code_verification_status",
    "name_status",
    "new_name_status",
    "account_mode",
    "platform_type",
}


class HostedMetaError(Exception):
    def __init__(self, message, *, status_code=None, code=None, subcode=None, trace_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.subcode = subcode
        self.trace_id = trace_id

    @property
    def access_state(self):
        if self.code == 190 or self.status_code == 401:
            return "token_expired"
        if self.code in {10, 200} or self.status_code in {403, 404}:
            return "access_denied"
        return "error"

    def public_dict(self):
        return {
            "message": str(self)[:1000],
            "status_code": self.status_code,
            "code": self.code,
            "subcode": self.subcode,
            "trace_id": self.trace_id,
            "access_state": self.access_state,
        }


class TemporaryMetaClient:
    def __init__(self, access_token, session=None):
        self.access_token = access_token
        self.session = session or requests.Session()

    def get(self, path_or_url, params=None):
        url = path_or_url if path_or_url.startswith("https://") else f"{GRAPH_BASE}/{path_or_url.lstrip('/')}"
        try:
            response = self.session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=(5, 20),
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise HostedMetaError(f"Meta request failed: {exc}") from exc
        if 300 <= response.status_code < 400:
            raise HostedMetaError("Meta returned an unexpected redirect", status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise HostedMetaError("Meta returned a non-JSON response", status_code=response.status_code) from exc
        if response.ok:
            return payload
        error = payload.get("error") or {}
        raise HostedMetaError(
            error.get("error_user_msg") or error.get("message") or f"Meta HTTP {response.status_code}",
            status_code=response.status_code,
            code=error.get("code"),
            subcode=error.get("error_subcode"),
            trace_id=error.get("fbtrace_id"),
        )

    def get_all(self, path, params=None):
        rows = []
        url = path
        next_params = params
        while url:
            payload = self.get(url, next_params)
            rows.extend(payload.get("data") or [])
            url = (payload.get("paging") or {}).get("next")
            next_params = None
        return rows

    def phone_numbers(self, waba_id):
        return self.get_all(
            f"{waba_id}/phone_numbers",
            {"fields": ",".join(CORE_FIELDS), "limit": 100},
        )

    def phone_details(self, list_row):
        phone_id = str(list_row["id"])
        details = dict(list_row)
        unavailable = []
        try:
            details.update(
                self.get(phone_id, {"fields": ",".join([*CORE_FIELDS, *DETAIL_FIELDS])})
            )
            return details, unavailable
        except HostedMetaError as exc:
            if exc.code != 100 and exc.status_code not in {400}:
                raise
        for field in DETAIL_FIELDS:
            try:
                details.update(self.get(phone_id, {"fields": field}))
            except HostedMetaError as exc:
                if exc.code == 100 or exc.status_code in {400, 403, 404}:
                    unavailable.append(field)
                else:
                    raise
        return details, unavailable

    def template_access(self, waba_id):
        try:
            templates = self.get_all(
                f"{waba_id}/message_templates",
                {"fields": "id,name,status,language,category", "limit": 100},
            )
            return {
                "status": "available",
                "count": len(templates),
                "by_status": dict(Counter(str(row.get("status") or "UNKNOWN") for row in templates)),
                "error": None,
            }
        except HostedMetaError as exc:
            return {"status": "denied" if exc.access_state in {"access_denied", "token_expired"} else "error", "count": None, "by_status": {}, "error": exc.public_dict()}


def _local_dict(phone):
    return {
        "phone_number_id": str(phone.phone_number_id),
        "display_phone_number": phone.display_phone_number,
        "verified_name": phone.verified_name,
        "quality_rating": phone.quality_rating,
        "messaging_limit_tier": phone.messaging_limit_tier,
        "code_verification_status": phone.code_verification_status or None,
        "name_status": phone.name_status or None,
        "new_name_status": phone.new_name_status or None,
        "account_mode": phone.account_mode or None,
        "platform_type": phone.platform_type or None,
        "is_official_business_account": phone.is_official_business_account,
        "is_usable": phone.is_usable,
        "usability_reason": phone.usability_reason,
        "is_active": phone.is_active,
        "is_default": phone.is_default,
    }


def _comparison(local, meta, unavailable):
    differences = {}
    for field in COMPARE_FIELDS:
        if field in unavailable or field not in meta:
            continue
        if local.get(field) != meta.get(field):
            differences[field] = {"local": local.get(field), "meta": meta.get(field)}
    return {
        "classification": "field_mismatch" if differences else ("partial_meta_data" if unavailable else "exact_match"),
        "phone_number_id": local["phone_number_id"],
        "local": local,
        "meta": {field: meta.get(field) for field in ["id", *COMPARE_FIELDS] if field in meta},
        "differences": differences,
        "unavailable_fields": unavailable,
    }


def build_comparison(access_token: str, waba_ids: Iterable[str] = None, client=None):
    client = client or TemporaryMetaClient(access_token)
    queryset = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").order_by("waba_id")
    requested_ids = sorted({str(value) for value in (waba_ids or []) if value})
    if requested_ids:
        queryset = queryset.filter(waba_id__in=requested_ids)

    result_wabas = []
    summary = Counter()
    for waba in queryset:
        local_phones = list(waba.phone_numbers.all())
        local_by_id = {str(phone.phone_number_id): phone for phone in local_phones}
        waba_result = {
            "waba_id": str(waba.waba_id),
            "name": waba.name,
            "local_count": len(local_phones),
            "meta_count": None,
            "error": None,
            "template_management": None,
            "phones": [],
        }
        try:
            list_rows = client.phone_numbers(waba.waba_id)
            waba_result["meta_count"] = len(list_rows)
            meta_by_id = {str(row["id"]): row for row in list_rows if row.get("id")}
            for phone_id in sorted(set(local_by_id) | set(meta_by_id)):
                phone = local_by_id.get(phone_id)
                list_row = meta_by_id.get(phone_id)
                if phone and not list_row:
                    row = {"classification": "local_only", "phone_number_id": phone_id, "local": _local_dict(phone), "meta": None, "differences": {}, "unavailable_fields": []}
                elif list_row and not phone:
                    details, unavailable = client.phone_details(list_row)
                    row = {"classification": "meta_only", "phone_number_id": phone_id, "local": None, "meta": details, "differences": {}, "unavailable_fields": unavailable}
                else:
                    details, unavailable = client.phone_details(list_row)
                    row = _comparison(_local_dict(phone), details, unavailable)
                waba_result["phones"].append(row)
                summary[row["classification"]] += 1
            waba_result["template_management"] = client.template_access(waba.waba_id)
        except HostedMetaError as exc:
            waba_result["error"] = exc.public_dict()
            summary["waba_access_error"] += 1
        result_wabas.append(waba_result)

    missing_waba_ids = sorted(set(requested_ids) - {row["waba_id"] for row in result_wabas})
    for waba_id in missing_waba_ids:
        result_wabas.append({"waba_id": waba_id, "name": None, "local_count": 0, "meta_count": None, "error": {"message": "WABA is not present in the hosted database", "access_state": "error"}, "template_management": None, "phones": []})
        summary["waba_access_error"] += 1

    comparison = {
        "graph_api_version": GRAPH_VERSION,
        "wabas": result_wabas,
        "summary": dict(sorted(summary.items())),
    }
    digest = hashlib.sha256(json.dumps(comparison, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return comparison, digest


def apply_comparison(comparison):
    checked_at = timezone.now()
    changed = []
    skipped = []
    for waba_row in comparison["wabas"]:
        try:
            waba = WhatsAppBusinessAccount.objects.get(waba_id=waba_row["waba_id"])
        except WhatsAppBusinessAccount.DoesNotExist:
            skipped.append({"waba_id": waba_row["waba_id"], "reason": "WABA not found locally"})
            continue
        phones = {str(phone.phone_number_id): phone for phone in waba.phone_numbers.all()}
        if waba_row["error"]:
            error = waba_row["error"]
            for phone in phones.values():
                phone.meta_last_attempt_at = checked_at
                phone.meta_fetch_error_code = str(error.get("code") or error.get("status_code") or "meta_error")
                phone.meta_fetch_error_message = error.get("message") or "Meta fetch failed"
                phone.meta_access_state = error.get("access_state") or "error"
                phone.save(update_fields=["meta_last_attempt_at", "meta_fetch_error_code", "meta_fetch_error_message", "meta_access_state"])
            skipped.append({"waba_id": waba.waba_id, "reason": error.get("message")})
            continue

        with transaction.atomic():
            for row in waba_row["phones"]:
                phone = phones.get(row["phone_number_id"])
                if not phone:
                    skipped.append({"waba_id": waba.waba_id, "phone_number_id": row["phone_number_id"], "reason": "Meta-only number; creation is disabled"})
                    continue
                before = _local_dict(phone)
                phone.meta_last_attempt_at = checked_at
                phone.meta_last_checked_at = checked_at
                phone.meta_fetch_error_code = ""
                phone.meta_fetch_error_message = ""
                if row["classification"] == "local_only":
                    phone.meta_seen_in_waba = False
                    phone.meta_access_state = "not_in_waba"
                    phone.meta_status = "logged_out"
                    phone.meta_status_reason = "Existing ANK number was not returned by this WABA"
                else:
                    meta = row["meta"] or {}
                    phone.meta_seen_in_waba = True
                    phone.meta_access_state = "partial" if row["unavailable_fields"] else "reachable"
                    phone.meta_last_success_at = checked_at
                    phone.meta_details_snapshot = {**meta, "unavailable_fields": row["unavailable_fields"]}
                    phone.meta_status = "active"
                    phone.meta_status_reason = ""
                    for field in COMPARE_FIELDS:
                        if field not in meta:
                            continue
                        value = meta[field]
                        if value is None and field in BLANKABLE_DETAIL_FIELDS:
                            value = ""
                        elif value is None and field not in NULLABLE_DETAIL_FIELDS:
                            # Do not replace required local identity fields with
                            # null when Meta returns a sparse response.
                            continue
                        setattr(phone, field, value)
                phone.save()
                after = _local_dict(phone)
                if before != after or row["classification"] in {"local_only", "partial_meta_data"}:
                    changed.append({"waba_id": waba.waba_id, "phone_number_id": phone.phone_number_id, "classification": row["classification"], "before": before, "after": after})
    return {"changed": changed, "skipped": skipped, "changed_count": len(changed), "skipped_count": len(skipped)}


def hosted_snapshot(waba_ids=None):
    queryset = WhatsAppBusinessAccount.objects.prefetch_related("phone_numbers").order_by("waba_id")
    if waba_ids:
        queryset = queryset.filter(waba_id__in=waba_ids)
    return {
        "wabas": [
            {
                "waba_id": waba.waba_id,
                "name": waba.name,
                "is_active": waba.is_active,
                "numbers": [_local_dict(phone) for phone in waba.phone_numbers.all()],
            }
            for waba in queryset
        ]
    }
