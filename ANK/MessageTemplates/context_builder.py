from typing import Any, Dict, List, Tuple
from datetime import datetime, date, time
from django.utils import timezone

# ---- helpers ----


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return timezone.localtime(v).strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return str(v)


def _pick(obj: Any, fields: Tuple[str]) -> Dict[str, str]:
    out = {}
    if not obj:
        return out
    for f in fields:
        try:
            out[f] = _to_str(getattr(obj, f, ""))
        except Exception:
            out[f] = ""
    return out


# ---- field whitelists ----

GUEST_FIELDS = ("name", "email", "phone", "city", "nationality")

EVENT_FIELDS = (
    "name",
    "location",
    "venue",
    "start_date",
    "end_date",
    "pax",
    "bride_name",
    "groom_name",
)

REG_FIELDS = (
    "rsvp_status",
    "estimated_pax",
    "additional_guest_count",
    "name_on_message",
    "family_salutation",
    "title",
    "guest_group",
    "sub_guest_group",
    "initiated_on",
    "responded_on",
    "hamper_count",
)

TRAVEL_FIELDS = (
    "travel_type",
    "arrival",
    "arrival_date",
    "arrival_time",
    "airline",
    "arrival_details",
    "hotel_arrival_time",
    "return_travel",
    "departure",
    "departure_date",
    "departure_details",
)

ACCOM_FIELDS = (
    "room_count",
    "room_type",
    "bed_type",
    "check_in",
    "check_out",
    "rooming_remarks",
)

SESSION_FIELDS = (
    "title",
    "description",
    "start_time",
    "end_time",
    "date",
    "venue",
    "location",
)

# ---- collectors ----


def _collect_travel(reg) -> List[Dict[str, Any]]:
    rows = []
    try:
        for td in reg.travel_detail_assignments.all():
            d = _pick(td, TRAVEL_FIELDS)
            if td.session_registration and td.session_registration.session:
                d["session_title"] = _to_str(td.session_registration.session.title)
            rows.append(d)
    except Exception:
        pass
    return rows


def _collect_accommodations(reg) -> Tuple[List[Dict[str, Any]], int]:
    items, total = [], 0
    try:
        for acc in reg.accommodation_assignments.select_related(
            "event_hotel__hotel", "sharing_with"
        ):
            d = _pick(acc, ACCOM_FIELDS)
            total += 1
            hotel = getattr(getattr(acc, "event_hotel", None), "hotel", None)
            d["hotel_name"] = _to_str(getattr(hotel, "name", ""))
            d["hotel_city"] = _to_str(getattr(hotel, "city", ""))
            d["hotel_country"] = _to_str(getattr(hotel, "country", ""))
            d["sharing_with_name"] = _to_str(getattr(acc.sharing_with, "name", ""))
            items.append(d)
    except Exception:
        pass
    return items, total


def _collect_sessions(event) -> List[Dict[str, Any]]:
    rows = []
    try:
        for s in event.sessions.all().order_by("start_time", "date"):
            rows.append(_pick(s, SESSION_FIELDS))
    except Exception:
        pass
    return rows


# ---- main ----


def build_registration_context(reg) -> Dict[str, Any]:
    guest, event = getattr(reg, "guest", None), getattr(reg, "event", None)

    ctx = {
        "Guest": _pick(guest, GUEST_FIELDS),
        "Event": _pick(event, EVENT_FIELDS),
        "Registration": _pick(reg, REG_FIELDS),
    }

    # computed Guest.first_name
    gname = ctx["Guest"].get("name", "")
    ctx["Guest"]["first_name"] = gname.split()[0] if gname else ""

    # Event.date_range
    ev_start, ev_end = ctx["Event"].get("start_date", ""), ctx["Event"].get(
        "end_date", ""
    )
    ctx["Event"]["date_range"] = (
        f"{ev_start} – {ev_end}" if ev_start and ev_end else ev_start or ev_end
    )

    # Registration.pax_total
    try:
        ctx["Registration"]["pax_total"] = int(reg.estimated_pax or 0) + int(
            reg.additional_guest_count or 0
        )
    except Exception:
        ctx["Registration"]["pax_total"] = 0

    # Travel, Accommodation, Sessions
    ctx["Travel"] = _collect_travel(reg)
    acc_list, acc_count = _collect_accommodations(reg)
    ctx["Accommodation"] = acc_list
    ctx["AccommodationCount"] = acc_count
    ctx["Sessions"] = _collect_sessions(event) if event else []

    return ctx
