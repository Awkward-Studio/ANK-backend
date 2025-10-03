"""
Conversation orchestrator for capturing TravelDetail via WhatsApp.

Responsibilities:
- Decide next question (step) based on TravelDetail fields and session state.
- Send buttons for choice steps; text prompts for free-form steps.
- Parse + validate answers; write to TravelDetail; auto-advance.
- Resume from where the guest left off; avoid resending the same prompt.

Choice steps use button IDs like: "tc|<step>|<value>"
"""

import re
from datetime import datetime, time
from typing import Tuple, Optional, Dict, Any

from django.utils import timezone as dj_tz
from django.db import transaction

from Logistics.models.travel_details_models import TravelDetail
from Logistics.models.travel_detail_capture_session import TravelCaptureSession
from Events.models.event_registration_model import EventRegistration
from MessageTemplates.services.whatsapp import (
    send_freeform_text,
    send_choice_buttons,
)

# ---------- parsing helpers ----------
_date_rx = re.compile(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$")
_time_rx = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", re.I)


def _parse_date(s: str):
    m = _date_rx.match(s or "")
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return datetime(y, mo, d).date()
    except ValueError:
        return None


def _parse_time(s: str):
    m = _time_rx.match(s or "")
    if not m:
        return None
    hh, mm, ap = m.groups()
    hh, mm = int(hh), int(mm)
    if ap:
        ap = ap.lower()
        if ap == "pm" and hh < 12:
            hh += 12
        if ap == "am" and hh == 12:
            hh = 0
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return time(hh, mm)
    return None


def _yn(s: str) -> Optional[bool]:
    x = (s or "").strip().lower()
    if x in {"y", "yes", "yeah", "yup", "true"}:
        return True
    if x in {"n", "no", "nope", "false"}:
        return False
    return None


def _choice(s: str, choices: Dict[str, str]) -> Optional[str]:
    x = (s or "").strip().lower()
    for key in choices:
        if x == key.lower():
            return key
    return None


def _set_optional_text(v: str) -> Optional[str]:
    if not v:
        return None
    if v.strip().lower() in {"skip", "none", "na"}:
        return ""
    return v.strip()


# ---------- constants ----------
ARRIVAL_CHOICES = {
    "commercial": "Commercial",
    "local_pickup": "Local Pickup",
    "self": "Self",
}
TRAVEL_TYPE_CHOICES = {"Air": "Air", "Train": "Train", "Car": "Car"}

PROMPTS = {
    "travel_type": "How are you traveling?",
    "arrival": "How will you arrive?",
    "arrival_date": "What is your arrival date? Reply like 2025-10-03",
    "arrival_time": "What is your arrival time? Reply like 14:30 or 2:30pm",
    "airline": "What is the airline?",
    "flight_number": "What is your flight number?",
    "pnr": "What is your PNR? (optional, reply 'skip' to skip)",
    "arrival_details": "Any arrival details we should know (pickup location, notes)? (reply 'skip' to skip)",
    "hotel_arrival_time": "What time will you reach the hotel? (HH:MM, or 'skip')",
    "hotel_departure_time": "What time will you depart the hotel? (HH:MM, or 'skip')",
    "return_travel": "Do you have a return journey?",
    "departure": "How will you depart?",
    "departure_date": "What is your departure date? (YYYY-MM-DD)",
    "departure_time": "What is your departure time? (HH:MM)",
    "departure_airline": "Departure airline? (if applicable; or 'skip')",
    "departure_flight_number": "Departure flight/train number? (or 'skip')",
    "departure_pnr": "Departure PNR? (or 'skip')",
    "departure_details": "Any departure details (pickup spot/notes)? (or 'skip')",
    "done": "Thanks! We’ve recorded your travel details. You can reply later to update a field (e.g., 'change airline Indigo').",
}


# ---------- session/detail helpers ----------
def _get_or_create_session(reg: EventRegistration) -> TravelCaptureSession:
    sess, _ = TravelCaptureSession.objects.get_or_create(registration=reg)
    return sess


def _get_or_create_detail(reg: EventRegistration) -> TravelDetail:
    td = TravelDetail.objects.filter(event=reg.event, event_registrations=reg).first()
    if td:
        return td
    td = TravelDetail.objects.create(event=reg.event)
    td.event_registrations.add(reg)
    return td


# ---------- next step logic ----------
def _next_step(sess: TravelCaptureSession, td: TravelDetail) -> Optional[str]:
    if sess.step == "done":
        return None

    pending = []

    # core
    if not td.travel_type:
        pending.append("travel_type")
    if not td.arrival:
        pending.append("arrival")
    if not td.arrival_date:
        pending.append("arrival_date")
    if not td.arrival_time:
        pending.append("arrival_time")

    # commercial air specifics
    if td.travel_type == "Air" and td.arrival == "commercial":
        if not td.airline:
            pending.append("airline")
        if not td.flight_number:
            pending.append("flight_number")
        if td.pnr is None:
            pending.append("pnr")

    # optional arrival note, hotel times
    if td.arrival_details is None:
        pending.append("arrival_details")
    if td.hotel_arrival_time is None:
        pending.append("hotel_arrival_time")
    if td.hotel_departure_time is None:
        pending.append("hotel_departure_time")

    # return branch
    if td.return_travel is False and "return_travel" not in (sess.state or {}):
        pending.append("return_travel")
    elif td.return_travel is True:
        if not td.departure:
            pending.append("departure")
        if not td.departure_date:
            pending.append("departure_date")
        if not td.departure_time:
            pending.append("departure_time")
        if td.travel_type == "Air" and td.departure == "commercial":
            if td.departure_airline is None:
                pending.append("departure_airline")
            if td.departure_flight_number is None:
                pending.append("departure_flight_number")
            if td.departure_pnr is None:
                pending.append("departure_pnr")
        if td.departure_details is None:
            pending.append("departure_details")

    if not pending:
        return "done"
    return pending[0]


# ---------- public API ----------
def start_capture_after_opt_in(reg: EventRegistration, *, restart: bool = False) -> str:
    """
    Called when guest presses 'Yes' on your travel opt-in OR when using a wake word.
    If restart=True or session is complete, we reset to 'travel_type'; otherwise we continue.
    """
    sess = _get_or_create_session(reg)
    _get_or_create_detail(reg)
    if restart or sess.is_complete:
        sess.step = "travel_type"
        sess.is_complete = False
        sess.state = {}
    else:
        sess.step = sess.step or "travel_type"
    sess.last_msg_at = dj_tz.now()
    sess.save(update_fields=["step", "is_complete", "state", "last_msg_at"])
    return PROMPTS.get(sess.step, PROMPTS["travel_type"])


def resume_or_start(reg: EventRegistration) -> None:
    """Resume from saved step or start at 'travel_type' and send the appropriate next prompt."""
    sess = _get_or_create_session(reg)
    if not sess.step or sess.step in {"opt_in", ""}:
        start_capture_after_opt_in(reg, restart=False)
    send_next_prompt(reg)


def send_next_prompt(reg: EventRegistration) -> None:
    """
    Chooses buttons for choice steps; otherwise sends text prompt.
    Uses last_prompt_step to avoid repeating the same question accidentally.
    """
    sess = _get_or_create_session(reg)
    td = _get_or_create_detail(reg)

    step = _next_step(sess, td) if sess.step != "done" else None
    if not step or step == "done":
        send_freeform_text(reg.guest.phone, PROMPTS["done"])
        sess.step = "done"
        sess.is_complete = True
        sess.last_prompt_step = "done"
        sess.last_msg_at = dj_tz.now()
        sess.save(
            update_fields=["step", "is_complete", "last_prompt_step", "last_msg_at"]
        )
        return

    if sess.last_prompt_step == step:
        # Avoid resending the exact same prompt.
        return

    sess.step = step
    sess.last_prompt_step = step
    sess.last_msg_at = dj_tz.now()
    sess.save(update_fields=["step", "last_prompt_step", "last_msg_at"])

    # Buttons for choice steps
    if step == "travel_type":
        send_choice_buttons(
            reg.guest.phone,
            "How are you traveling?",
            [
                {"id": "tc|travel_type|Air", "title": "Air"},
                {"id": "tc|travel_type|Train", "title": "Train"},
                {"id": "tc|travel_type|Car", "title": "Car"},
            ],
        )
        return
    if step == "arrival":
        send_choice_buttons(
            reg.guest.phone,
            "How will you arrive?",
            [
                {"id": "tc|arrival|commercial", "title": "Commercial"},
                {"id": "tc|arrival|local_pickup", "title": "Local Pickup"},
                {"id": "tc|arrival|self", "title": "Self"},
            ],
        )
        return
    if step == "return_travel":
        send_choice_buttons(
            reg.guest.phone,
            "Do you have a return journey?",
            [
                {"id": "tc|return_travel|yes", "title": "Yes"},
                {"id": "tc|return_travel|no", "title": "No"},
            ],
        )
        return
    if step == "departure":
        send_choice_buttons(
            reg.guest.phone,
            "How will you depart?",
            [
                {"id": "tc|departure|commercial", "title": "Commercial"},
                {"id": "tc|departure|local_pickup", "title": "Local Pickup"},
                {"id": "tc|departure|self", "title": "Self"},
            ],
        )
        return

    # Free-form prompts for the rest
    send_freeform_text(reg.guest.phone, PROMPTS.get(step, "OK."))


@transaction.atomic
def apply_button_choice(reg: EventRegistration, step: str, raw_value: str) -> None:
    """
    Applies a button value to the appropriate TravelDetail field and advances to the next prompt.
    """
    td = _get_or_create_detail(reg)
    sess = _get_or_create_session(reg)

    if step == "travel_type" and raw_value in TRAVEL_TYPE_CHOICES:
        td.travel_type = raw_value
        td.save(update_fields=["travel_type"])
    elif step == "arrival" and raw_value in ARRIVAL_CHOICES:
        td.arrival = raw_value
        td.save(update_fields=["arrival"])
    elif step == "return_travel":
        td.return_travel = raw_value == "yes"
        td.save(update_fields=["return_travel"])
        sess.state["return_travel"] = td.return_travel
    elif step == "departure" and raw_value in ARRIVAL_CHOICES:
        td.departure = raw_value
        td.save(update_fields=["departure"])

    send_next_prompt(reg)


@transaction.atomic
def handle_inbound_answer(reg: EventRegistration, text: str) -> Tuple[str, bool]:
    """
    Handles typed (free-text) answers for non-choice steps.
    Returns (reply_text, completed_flag).
    """
    sess = _get_or_create_session(reg)
    td = _get_or_create_detail(reg)

    if sess.step in {"opt_in", ""}:
        sess.step = "travel_type"

    step = sess.step or "travel_type"
    t = (text or "").strip()

    if step == "travel_type":
        val = _choice(t, TRAVEL_TYPE_CHOICES)
        if not val:
            return ("Please tap a button or reply: Air / Train / Car", False)
        td.travel_type = val
        td.save(update_fields=["travel_type"])

    elif step == "arrival":
        val = _choice(t, ARRIVAL_CHOICES)
        if not val:
            return (
                "Please tap a button or reply: commercial / local_pickup / self",
                False,
            )
        td.arrival = val
        td.save(update_fields=["arrival"])

    elif step == "arrival_date":
        dt = _parse_date(t)
        if not dt:
            return ("Please send date as YYYY-MM-DD (e.g., 2025-10-03).", False)
        td.arrival_date = dt
        td.save(update_fields=["arrival_date"])

    elif step == "arrival_time":
        tm = _parse_time(t)
        if not tm:
            return ("Please send time like 14:30 or 2:30pm.", False)
        td.arrival_time = tm
        td.save(update_fields=["arrival_time"])

    elif step == "airline":
        td.airline = t
        td.save(update_fields=["airline"])

    elif step == "flight_number":
        td.flight_number = t.upper()
        td.save(update_fields=["flight_number"])

    elif step == "pnr":
        td.pnr = _set_optional_text(t)
        td.save(update_fields=["pnr"])

    elif step == "arrival_details":
        td.arrival_details = _set_optional_text(t)
        td.save(update_fields=["arrival_details"])

    elif step == "hotel_arrival_time":
        if t.lower() in {"skip", ""}:
            td.hotel_arrival_time = None
        else:
            tm = _parse_time(t)
            if not tm:
                return ("Time looks off. Example: 13:45", False)
            td.hotel_arrival_time = tm
        td.save(update_fields=["hotel_arrival_time"])

    elif step == "hotel_departure_time":
        if t.lower() in {"skip", ""}:
            td.hotel_departure_time = None
        else:
            tm = _parse_time(t)
            if not tm:
                return ("Time looks off. Example: 10:00", False)
            td.hotel_departure_time = tm
        td.save(update_fields=["hotel_departure_time"])

    elif step == "return_travel":
        b = _yn(t)
        if b is None:
            return ("Please tap Yes/No.", False)
        td.return_travel = b
        td.save(update_fields=["return_travel"])
        sess.state["return_travel"] = b

    elif step == "departure":
        val = _choice(t, ARRIVAL_CHOICES)
        if not val:
            return (
                "Please tap a button or reply: commercial / local_pickup / self",
                False,
            )
        td.departure = val
        td.save(update_fields=["departure"])

    elif step == "departure_date":
        dt = _parse_date(t)
        if not dt:
            return ("Send date as YYYY-MM-DD", False)
        td.departure_date = dt
        td.save(update_fields=["departure_date"])

    elif step == "departure_time":
        tm = _parse_time(t)
        if not tm:
            return ("Send time like 18:20 or 6:20pm", False)
        td.departure_time = tm
        td.save(update_fields=["departure_time"])

    elif step == "departure_airline":
        td.departure_airline = _set_optional_text(t)
        td.save(update_fields=["departure_airline"])

    elif step == "departure_flight_number":
        td.departure_flight_number = _set_optional_text(t)
        td.save(update_fields=["departure_flight_number"])

    elif step == "departure_pnr":
        td.departure_pnr = _set_optional_text(t)
        td.save(update_fields=["departure_pnr"])

    elif step == "departure_details":
        td.departure_details = _set_optional_text(t)
        td.save(update_fields=["departure_details"])

    # advance
    sess.step = _next_step(sess, td) or "done"
    sess.last_msg_at = dj_tz.now()
    if sess.step == "done":
        sess.is_complete = True
    sess.save(update_fields=["step", "last_msg_at", "is_complete"])

    done = sess.step == "done"
    if done:
        return (PROMPTS["done"], True)
    return (PROMPTS.get(sess.step, "OK."), False)
