"""
Conversation orchestrator for capturing TravelDetail via WhatsApp.

Responsibilities:
- Decide next question (step) based on TravelDetail fields and session state.
- Send buttons for choice steps; text prompts for free-form steps.
- Parse + validate answers; write to TravelDetail; auto-advance.
- Resume from where the guest left off.
- If a step was sent but not answered and the flow is started again,
  resend the same pending step.
"""

import re
import logging
from datetime import datetime, time
from typing import Tuple, Optional, Dict

from django.utils import timezone as dj_tz
from django.db import transaction

from Logistics.models.travel_details_models import TravelDetail
from Logistics.models.travel_detail_capture_session import TravelCaptureSession
from Events.models.event_registration_model import EventRegistration
from MessageTemplates.services.whatsapp import (
    send_freeform_text,
    send_choice_buttons,
)

logger = logging.getLogger("whatsapp")

# ---------- parsing helpers ----------

_date_rx = re.compile(r"^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*$")
_time_rx = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", re.I)


def _parse_date(s: str):
    m = _date_rx.match(s or "")
    if not m:
        return None
    d, mo, y = map(int, m.groups())
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
    """
    Optional text fields:
    - Treat empty / 'skip' / 'none' / 'na' / 'n/a' / '-' as *skipped* → store "".
    - Anything else: trimmed string.
    We use session state flags to know if we already asked this field.
    """
    if v is None:
        return ""
    s = v.strip()
    if not s:
        return ""
    sl = s.lower()
    if sl in {"skip", "none", "na", "n/a", "-"}:
        return ""
    return s


# ---------- constants ----------

ARRIVAL_CHOICES = {
    "commercial": "Commercial",
    "local_pickup": "Local Pickup",
    "self": "Self",
}
TRAVEL_TYPE_CHOICES = {"Air": "Air", "Train": "Train", "Car": "Car"}

# Steps that should always be rendered as WhatsApp buttons
CHOICE_STEPS = {"travel_type", "arrival", "return_travel", "departure"}

PROMPTS = {
    "travel_type": "How are you traveling?",
    "arrival": "How will you arrive?",
    "arrival_date": "What is your arrival date? Reply like 03-10-2025",
    "arrival_time": "What is your arrival time? Reply like 14:30 or 2:30pm",
    "airline": "What is the airline?",
    "flight_number": "What is your flight number?",
    "pnr": "What is your PNR? (optional, reply 'skip' to skip)",
    "arrival_details": "Any arrival details we should know (pickup location, notes)? (reply 'skip' to skip)",
    "hotel_arrival_time": "What time will you reach the hotel? (HH:MM, or 'skip')",
    "hotel_departure_time": "What time will you depart the hotel? (HH:MM, or 'skip')",
    "return_travel": "Do you have a return journey?",
    "departure": "How will you depart?",
    "departure_date": "What is your departure date? (DD-MM-YYYY)",
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
    if sess.state is None:
        sess.state = {}
        sess.save(update_fields=["state"])
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
    """
    Decide the next logical step based on what is already stored.
    We rely on TravelDetail fields + session.state flags to know what has been asked.
    """
    if sess.step == "done":
        return None

    state = sess.state or {}
    pending = []

    # --- core arrival stuff ---
    if not td.travel_type:
        pending.append("travel_type")
    if not td.arrival:
        pending.append("arrival")
    if not td.arrival_date:
        pending.append("arrival_date")
    if not td.arrival_time:
        pending.append("arrival_time")

    # --- inbound commercial air specifics ---
    if td.travel_type == "Air" and td.arrival == "commercial":
        if not td.airline:
            pending.append("airline")
        if not td.flight_number:
            pending.append("flight_number")
        # pnr: optional but we want to ask once per flow
        if not state.get("pnr_done"):
            pending.append("pnr")

    # --- arrival details; ask once per flow, may be skipped ---
    if not state.get("arrival_details_done"):
        pending.append("arrival_details")

    # --- Hotel times: allow skipping via flags so we don't re-ask ---
    if td.hotel_arrival_time is None and not state.get("hat_skip"):
        pending.append("hotel_arrival_time")
    if td.hotel_departure_time is None and not state.get("hdt_skip"):
        pending.append("hotel_departure_time")

    # --- Return travel decision; ask once per flow ---
    if not state.get("return_travel_done"):
        pending.append("return_travel")
    elif state.get("return_travel_done") and td.return_travel:
        # Departure only if user said they have return travel
        if not td.departure:
            pending.append("departure")
        if not td.departure_date:
            pending.append("departure_date")
        if not td.departure_time:
            pending.append("departure_time")

        if td.travel_type == "Air" and td.departure == "commercial":
            if not state.get("departure_airline_done"):
                pending.append("departure_airline")
            if not state.get("departure_flight_number_done"):
                pending.append("departure_flight_number")
            if not state.get("departure_pnr_done"):
                pending.append("departure_pnr")

        if not state.get("departure_details_done"):
            pending.append("departure_details")

    if not pending:
        return "done"
    return pending[0]


# ---------- public API ----------


def start_capture_after_opt_in(reg: EventRegistration, *, restart: bool = False) -> str:
    """
    Called when guest opts in / flow explicitly started.
    If restart=True, we reset the session to the beginning.
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

    send_next_prompt(reg)
    return sess.step


def resume_or_start(reg: EventRegistration) -> None:
    """
    Called on WAKE/RESUME from WhatsApp.

    If the flow is already complete, we *do not* auto-restart here.
    (Use start_capture_after_opt_in(restart=True) from your UI if you want a hard reset.)
    """
    sess = _get_or_create_session(reg)

    if sess.is_complete or sess.step == "done":
        logger.warning(
            f"[RESUME] Registration={reg.pk} session already complete; not sending more prompts."
        )
        return

    if not sess.step or sess.step in {"opt_in", ""}:
        start_capture_after_opt_in(reg, restart=False)
        return

    send_next_prompt(reg)


def _send_whatsapp_prompt(reg: EventRegistration, step: str) -> None:
    """
    Internal helper: send exactly ONE WA message for this step.
    """
    phone = reg.guest.phone
    logger.warning(f"[PROMPT] Sending step '{step}' to {phone}")

    # Buttons for choice steps
    if step == "travel_type":
        send_choice_buttons(
            phone,
            PROMPTS["travel_type"],
            [
                {"id": "tc|travel_type|Air", "title": "Air"},
                {"id": "tc|travel_type|Train", "title": "Train"},
                {"id": "tc|travel_type|Car", "title": "Car"},
            ],
        )
        return

    if step == "arrival":
        send_choice_buttons(
            phone,
            PROMPTS["arrival"],
            [
                {"id": "tc|arrival|commercial", "title": "Commercial"},
                {"id": "tc|arrival|local_pickup", "title": "Local Pickup"},
                {"id": "tc|arrival|self", "title": "Self"},
            ],
        )
        return

    if step == "return_travel":
        send_choice_buttons(
            phone,
            PROMPTS["return_travel"],
            [
                {"id": "tc|return_travel|yes", "title": "Yes"},
                {"id": "tc|return_travel|no", "title": "No"},
            ],
        )
        return

    if step == "departure":
        send_choice_buttons(
            phone,
            PROMPTS["departure"],
            [
                {"id": "tc|departure|commercial", "title": "Commercial"},
                {"id": "tc|departure|local_pickup", "title": "Local Pickup"},
                {"id": "tc|departure|self", "title": "Self"},
            ],
        )
        return

    # Free-form for the rest
    send_freeform_text(phone, PROMPTS.get(step, "OK."))


def send_next_prompt(reg: EventRegistration) -> None:
    """
    Decide next step from TravelDetail + session.
    Sends exactly one WA message for that step.
    If message send fails, we log & DO NOT advance step,
    so next resume can retry.
    """
    sess = _get_or_create_session(reg)
    td = _get_or_create_detail(reg)

    step = _next_step(sess, td) if sess.step != "done" else None
    logger.warning(f"[STEP] next_step={step!r} (current sess.step={sess.step!r})")

    if not step:
        logger.warning("[STEP] No step (None); nothing to send.")
        return

    if step == "done":
        # Final message, then mark complete
        try:
            logger.warning(f"[PROMPT] Sending DONE to {reg.guest.phone}")
            send_freeform_text(reg.guest.phone, PROMPTS["done"])
        except Exception:
            logger.exception("[ERROR] Failed to send DONE message on WhatsApp")
            # Even if WA fails, mark as complete — data is there

        sess.step = "done"
        sess.is_complete = True
        sess.last_prompt_step = "done"
        sess.last_msg_at = dj_tz.now()
        sess.save(
            update_fields=["step", "is_complete", "last_prompt_step", "last_msg_at"]
        )
        return

    # If the same step is still pending (unanswered) and flow is resumed,
    # we want to resend it. So we always send whatever _next_step says.

    try:
        _send_whatsapp_prompt(reg, step)
    except Exception:
        logger.exception(f"[ERROR] Failed to send WA prompt for step={step}")
        # Do NOT advance; let the next WAKE try again
        return

    # Only if send succeeded do we record that we prompted this step
    sess.step = step
    sess.last_prompt_step = step
    sess.last_msg_at = dj_tz.now()
    sess.save(update_fields=["step", "last_prompt_step", "last_msg_at"])


# ---------- button handling ----------


@transaction.atomic
def apply_button_choice(reg: EventRegistration, step: str, raw_value: str) -> None:
    """
    Applies a button value to the appropriate TravelDetail field and advances to the next prompt.
    """
    td = _get_or_create_detail(reg)
    sess = _get_or_create_session(reg)

    try:
        if step == "travel_type" and raw_value in TRAVEL_TYPE_CHOICES:
            td.travel_type = raw_value
            td.save(update_fields=["travel_type"])

        elif step == "arrival" and raw_value in ARRIVAL_CHOICES:
            td.arrival = raw_value
            td.save(update_fields=["arrival"])

        elif step == "return_travel":
            # mark answered in state, and store boolean in td
            sess.state = sess.state or {}
            sess.state["return_travel_done"] = True
            td.return_travel = raw_value == "yes"
            td.save(update_fields=["return_travel"])
            sess.save(update_fields=["state"])

        elif step == "departure" and raw_value in ARRIVAL_CHOICES:
            td.departure = raw_value
            td.save(update_fields=["departure"])

        else:
            logger.warning(
                f"[BUTTON] Unknown or invalid step/value: step={step!r} value={raw_value!r}"
            )
            return
    except Exception:
        logger.exception(f"[ERROR] Failed to apply button choice for step={step}")
        return

    # After applying choice, move to next step via centralized prompt logic
    try:
        send_next_prompt(reg)
    except Exception:
        logger.exception("[ERROR] Failed in send_next_prompt after button choice")


# ---------- free-text handling ----------


@transaction.atomic
def handle_inbound_answer(reg: EventRegistration, text: str) -> Tuple[str, bool]:
    """
    Handles typed (free-text) answers for the *current* step.

    Returns:
      - reply_text: only for validation errors or "try again" messages.
                    On success, we return "" and let send_next_prompt() send the next WA message.
      - completed_flag: True if after this answer the flow is completed.
    """
    sess = _get_or_create_session(reg)
    td = _get_or_create_detail(reg)

    # If somehow we got text without an active step, start at travel_type
    if not sess.step or sess.step in {"opt_in", ""}:
        sess.step = "travel_type"
        sess.save(update_fields=["step"])

    step = sess.step or "travel_type"
    t = (text or "").strip()
    logger.warning(f"[ANSWER] step={step!r} text={t!r}")

    state_changed = False

    try:
        # --- Choice steps typed as text (we still support typing "Air", "Yes", etc.) ---
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
                    "Please tap a button or reply: Commercial / Local Pickup / Self",
                    False,
                )
            td.arrival = val
            td.save(update_fields=["arrival"])

        elif step == "return_travel":
            b = _yn(t)
            if b is None:
                return ("Please tap Yes/No.", False)
            td.return_travel = b
            sess.state = sess.state or {}
            sess.state["return_travel_done"] = True
            state_changed = True
            td.save(update_fields=["return_travel"])

        elif step == "departure":
            val = _choice(t, ARRIVAL_CHOICES)
            if not val:
                return (
                    "Please tap a button or reply: Commercial / Local Pickup / Self",
                    False,
                )
            td.departure = val
            td.save(update_fields=["departure"])

        # --- Pure free-text / date / time steps ---
        elif step == "arrival_date":
            dt = _parse_date(t)
            if not dt:
                return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
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
            sess.state = sess.state or {}
            sess.state["pnr_done"] = True
            state_changed = True
            td.save(update_fields=["pnr"])

        elif step == "arrival_details":
            td.arrival_details = _set_optional_text(t)
            sess.state = sess.state or {}
            sess.state["arrival_details_done"] = True
            state_changed = True
            td.save(update_fields=["arrival_details"])

        elif step == "hotel_arrival_time":
            key = t.strip().lower()
            sess.state = sess.state or {}
            if key in {"skip", "none", "na", "n/a", ""}:
                td.hotel_arrival_time = None
                sess.state["hat_skip"] = True
            else:
                tm = _parse_time(t)
                if not tm:
                    return ("Time looks off. Example: 13:45", False)
                td.hotel_arrival_time = tm
                sess.state.pop("hat_skip", None)
            state_changed = True
            td.save(update_fields=["hotel_arrival_time"])

        elif step == "hotel_departure_time":
            key = t.strip().lower()
            sess.state = sess.state or {}
            if key in {"skip", "none", "na", "n/a", ""}:
                td.hotel_departure_time = None
                sess.state["hdt_skip"] = True
            else:
                tm = _parse_time(t)
                if not tm:
                    return ("Time looks off. Example: 10:00", False)
                td.hotel_departure_time = tm
                sess.state.pop("hdt_skip", None)
            state_changed = True
            td.save(update_fields=["hotel_departure_time"])

        elif step == "departure_date":
            dt = _parse_date(t)
            if not dt:
                return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
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
            sess.state = sess.state or {}
            sess.state["departure_airline_done"] = True
            state_changed = True
            td.save(update_fields=["departure_airline"])

        elif step == "departure_flight_number":
            td.departure_flight_number = _set_optional_text(t)
            sess.state = sess.state or {}
            sess.state["departure_flight_number_done"] = True
            state_changed = True
            td.save(update_fields=["departure_flight_number"])

        elif step == "departure_pnr":
            td.departure_pnr = _set_optional_text(t)
            sess.state = sess.state or {}
            sess.state["departure_pnr_done"] = True
            state_changed = True
            td.save(update_fields=["departure_pnr"])

        elif step == "departure_details":
            td.departure_details = _set_optional_text(t)
            sess.state = sess.state or {}
            sess.state["departure_details_done"] = True
            state_changed = True
            td.save(update_fields=["departure_details"])

        else:
            logger.warning(f"[ANSWER] Unknown step={step!r}, text={t!r}")
            return ("Sorry, I didn't understand that. Please try again.", False)

    except Exception:
        logger.exception(f"[ERROR] Failed while handling inbound answer at step={step}")
        return (
            "Something went wrong while saving your answer. Please try again.",
            False,
        )

    # Persist session meta (but NOT step/is_complete; send_next_prompt will decide next step)
    sess.last_msg_at = dj_tz.now()
    if state_changed:
        try:
            sess.save(update_fields=["last_msg_at", "state"])
        except Exception:
            logger.exception(
                "[ERROR] Failed to save session after inbound answer (state)"
            )
    else:
        try:
            sess.save(update_fields=["last_msg_at"])
        except Exception:
            logger.exception(
                "[ERROR] Failed to save session after inbound answer (no state change)"
            )

    # We successfully stored the answer → now send whatever the *next* prompt is.
    try:
        send_next_prompt(reg)
    except Exception:
        logger.exception("[ERROR] Failed in send_next_prompt after inbound answer")
        return (
            "Something went wrong while sending the next question. Please try again.",
            False,
        )

    # Refresh to know if we're done
    sess.refresh_from_db()
    done = bool(sess.is_complete)

    # We already sent the next prompt (or DONE) inside send_next_prompt,
    # so we return empty reply_text here.
    return ("", done)


# """
# Conversation orchestrator for capturing TravelDetail via WhatsApp.

# Responsibilities:
# - Decide next question (step) based on TravelDetail fields and session state.
# - Send buttons for choice steps; text prompts for free-form steps.
# - Parse + validate answers; write to TravelDetail; auto-advance.
# - Resume from where the guest left off.
# - If a step was sent but not answered and the flow is started again,
#   resend the same pending step.
# """

# import re
# import logging
# from datetime import datetime, time
# from typing import Tuple, Optional, Dict, Any

# from django.utils import timezone as dj_tz
# from django.db import transaction

# from Logistics.models.travel_details_models import TravelDetail
# from Logistics.models.travel_detail_capture_session import TravelCaptureSession
# from Events.models.event_registration_model import EventRegistration
# from MessageTemplates.services.whatsapp import (
#     send_freeform_text,
#     send_choice_buttons,
# )

# logger = logging.getLogger("whatsapp")

# # ---------- parsing helpers ----------
# _date_rx = re.compile(r"^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*$")
# _time_rx = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", re.I)


# def _parse_date(s: str):
#     m = _date_rx.match(s or "")
#     if not m:
#         return None
#     d, mo, y = map(int, m.groups())
#     try:
#         return datetime(y, mo, d).date()
#     except ValueError:
#         return None


# def _parse_time(s: str):
#     m = _time_rx.match(s or "")
#     if not m:
#         return None
#     hh, mm, ap = m.groups()
#     hh, mm = int(hh), int(mm)
#     if ap:
#         ap = ap.lower()
#         if ap == "pm" and hh < 12:
#             hh += 12
#         if ap == "am" and hh == 12:
#             hh = 0
#     if 0 <= hh <= 23 and 0 <= mm <= 59:
#         return time(hh, mm)
#     return None


# def _yn(s: str) -> Optional[bool]:
#     x = (s or "").strip().lower()
#     if x in {"y", "yes", "yeah", "yup", "true"}:
#         return True
#     if x in {"n", "no", "nope", "false"}:
#         return False
#     return None


# def _choice(s: str, choices: Dict[str, str]) -> Optional[str]:
#     x = (s or "").strip().lower()
#     for key in choices:
#         if x == key.lower():
#             return key
#     return None


# def _set_optional_text(v: str) -> Optional[str]:
#     """
#     Optional text fields:
#     - Treat empty / 'skip' / 'none' / 'na' / 'n/a' / '-' as *skipped* → store "".
#     - Anything else: trimmed string.
#     We use session state flags to know if we already asked this field.
#     """
#     if v is None:
#         return ""
#     s = v.strip()
#     if not s:
#         return ""
#     sl = s.lower()
#     if sl in {"skip", "none", "na", "n/a", "-"}:
#         return ""
#     return s


# # ---------- constants ----------
# ARRIVAL_CHOICES = {
#     "commercial": "Commercial",
#     "local_pickup": "Local Pickup",
#     "self": "Self",
# }
# TRAVEL_TYPE_CHOICES = {"Air": "Air", "Train": "Train", "Car": "Car"}

# PROMPTS = {
#     "travel_type": "How are you traveling?",
#     "arrival": "How will you arrive?",
#     "arrival_date": "What is your arrival date? Reply like 03-10-2025",
#     "arrival_time": "What is your arrival time? Reply like 14:30 or 2:30pm",
#     "airline": "What is the airline?",
#     "flight_number": "What is your flight number?",
#     "pnr": "What is your PNR? (optional, reply 'skip' to skip)",
#     "arrival_details": "Any arrival details we should know (pickup location, notes)? (reply 'skip' to skip)",
#     "hotel_arrival_time": "What time will you reach the hotel? (HH:MM, or 'skip')",
#     "hotel_departure_time": "What time will you depart the hotel? (HH:MM, or 'skip')",
#     "return_travel": "Do you have a return journey?",
#     "departure": "How will you depart?",
#     "departure_date": "What is your departure date? (DD-MM-YYYY)",
#     "departure_time": "What is your departure time? (HH:MM)",
#     "departure_airline": "Departure airline? (if applicable; or 'skip')",
#     "departure_flight_number": "Departure flight/train number? (or 'skip')",
#     "departure_pnr": "Departure PNR? (or 'skip')",
#     "departure_details": "Any departure details (pickup spot/notes)? (or 'skip')",
#     "done": "Thanks! We’ve recorded your travel details. You can reply later to update a field (e.g., 'change airline Indigo').",
# }


# # ---------- session/detail helpers ----------
# def _get_or_create_session(reg: EventRegistration) -> TravelCaptureSession:
#     sess, _ = TravelCaptureSession.objects.get_or_create(registration=reg)
#     if sess.state is None:
#         sess.state = {}
#         sess.save(update_fields=["state"])
#     return sess


# def _get_or_create_detail(reg: EventRegistration) -> TravelDetail:
#     td = TravelDetail.objects.filter(event=reg.event, event_registrations=reg).first()
#     if td:
#         return td
#     td = TravelDetail.objects.create(event=reg.event)
#     td.event_registrations.add(reg)
#     return td


# # ---------- next step logic ----------
# def _next_step(sess: TravelCaptureSession, td: TravelDetail) -> Optional[str]:
#     """
#     Decide the next logical step based on what is already stored.
#     We rely on TravelDetail fields + session.state flags to know what has been asked.
#     """
#     if sess.step == "done":
#         return None

#     state = sess.state or {}
#     pending = []

#     # --- core arrival stuff ---
#     if not td.travel_type:
#         pending.append("travel_type")
#     if not td.arrival:
#         pending.append("arrival")
#     if not td.arrival_date:
#         pending.append("arrival_date")
#     if not td.arrival_time:
#         pending.append("arrival_time")

#     # --- inbound commercial air specifics ---
#     if td.travel_type == "Air" and td.arrival == "commercial":
#         if not td.airline:
#             pending.append("airline")
#         if not td.flight_number:
#             pending.append("flight_number")
#         # pnr: optional but we want to ask once per flow
#         if not state.get("pnr_done"):
#             pending.append("pnr")

#     # --- arrival details; ask once per flow, may be skipped ---
#     if not state.get("arrival_details_done"):
#         pending.append("arrival_details")

#     # --- Hotel times: allow skipping via flags so we don't re-ask ---
#     if td.hotel_arrival_time is None and not state.get("hat_skip"):
#         pending.append("hotel_arrival_time")
#     if td.hotel_departure_time is None and not state.get("hdt_skip"):
#         pending.append("hotel_departure_time")

#     # --- Return travel decision; ask once per flow ---
#     if not state.get("return_travel_done"):
#         pending.append("return_travel")
#     elif state.get("return_travel_done") and td.return_travel:
#         # Departure only if user said they have return travel
#         if not td.departure:
#             pending.append("departure")
#         if not td.departure_date:
#             pending.append("departure_date")
#         if not td.departure_time:
#             pending.append("departure_time")

#         if td.travel_type == "Air" and td.departure == "commercial":
#             if not state.get("departure_airline_done"):
#                 pending.append("departure_airline")
#             if not state.get("departure_flight_number_done"):
#                 pending.append("departure_flight_number")
#             if not state.get("departure_pnr_done"):
#                 pending.append("departure_pnr")

#         if not state.get("departure_details_done"):
#             pending.append("departure_details")

#     if not pending:
#         return "done"
#     return pending[0]


# # ---------- public API ----------
# def start_capture_after_opt_in(reg: EventRegistration, *, restart: bool = False) -> str:
#     """
#     Called when guest opts in / flow explicitly started.
#     If restart=True, we reset the session to the beginning.
#     """
#     sess = _get_or_create_session(reg)
#     _get_or_create_detail(reg)

#     if restart or sess.is_complete:
#         sess.step = "travel_type"
#         sess.is_complete = False
#         sess.state = {}
#     else:
#         sess.step = sess.step or "travel_type"

#     sess.last_msg_at = dj_tz.now()
#     sess.save(update_fields=["step", "is_complete", "state", "last_msg_at"])

#     send_next_prompt(reg)
#     return sess.step


# def resume_or_start(reg: EventRegistration) -> None:
#     """
#     Called on WAKE.

#     If the flow is already complete, do nothing.
#     (You can wire a response later.)
#     """
#     sess = _get_or_create_session(reg)

#     if sess.is_complete or sess.step == "done":
#         logger.warning(
#             f"[RESUME] Registration={reg.pk} session already complete; not sending more prompts."
#         )
#         # TODO: later you can return something like:
#         # return {"status": "completed"}
#         return

#     if not sess.step or sess.step in {"opt_in", ""}:
#         start_capture_after_opt_in(reg, restart=False)
#         return

#     send_next_prompt(reg)


# def _send_whatsapp_prompt(reg: EventRegistration, step: str) -> None:
#     """
#     Internal helper: send exactly ONE WA message for this step.
#     """
#     phone = reg.guest.phone
#     logger.warning(f"[PROMPT] Sending step '{step}' to {phone}")

#     # Buttons for choice steps
#     if step == "travel_type":
#         send_choice_buttons(
#             phone,
#             PROMPTS["travel_type"],
#             [
#                 {"id": "tc|travel_type|Air", "title": "Air"},
#                 {"id": "tc|travel_type|Train", "title": "Train"},
#                 {"id": "tc|travel_type|Car", "title": "Car"},
#             ],
#         )
#         return

#     if step == "arrival":
#         send_choice_buttons(
#             phone,
#             PROMPTS["arrival"],
#             [
#                 {"id": "tc|arrival|commercial", "title": "Commercial"},
#                 {"id": "tc|arrival|local_pickup", "title": "Local Pickup"},
#                 {"id": "tc|arrival|self", "title": "Self"},
#             ],
#         )
#         return

#     if step == "return_travel":
#         send_choice_buttons(
#             phone,
#             PROMPTS["return_travel"],
#             [
#                 {"id": "tc|return_travel|yes", "title": "Yes"},
#                 {"id": "tc|return_travel|no", "title": "No"},
#             ],
#         )
#         return

#     if step == "departure":
#         send_choice_buttons(
#             phone,
#             PROMPTS["departure"],
#             [
#                 {"id": "tc|departure|commercial", "title": "Commercial"},
#                 {"id": "tc|departure|local_pickup", "title": "Local Pickup"},
#                 {"id": "tc|departure|self", "title": "Self"},
#             ],
#         )
#         return

#     # Free-form for the rest
#     send_freeform_text(phone, PROMPTS.get(step, "OK."))


# def send_next_prompt(reg: EventRegistration) -> None:
#     """
#     Decide next step from TravelDetail + session.
#     Sends exactly one WA message for that step.
#     If message send fails, we log & DO NOT advance step,
#     so next resume can retry.
#     """
#     sess = _get_or_create_session(reg)
#     td = _get_or_create_detail(reg)

#     step = _next_step(sess, td) if sess.step != "done" else None
#     logger.warning(f"[STEP] next_step={step!r} (current sess.step={sess.step!r})")

#     if not step:
#         logger.warning("[STEP] No step (None); nothing to send.")
#         return

#     if step == "done":
#         # Final message, then mark complete
#         try:
#             logger.warning(f"[PROMPT] Sending DONE to {reg.guest.phone}")
#             send_freeform_text(reg.guest.phone, PROMPTS["done"])
#         except Exception:
#             logger.exception("[ERROR] Failed to send DONE message on WhatsApp")
#             # Even if WA fails, mark as complete — data is there
#         sess.step = "done"
#         sess.is_complete = True
#         sess.last_prompt_step = "done"
#         sess.last_msg_at = dj_tz.now()
#         sess.save(
#             update_fields=["step", "is_complete", "last_prompt_step", "last_msg_at"]
#         )
#         return

#     # We DO NOT block on last_prompt_step anymore.
#     # If the same step is still pending (unanswered) and flow is resumed,
#     # we want to resend it.

#     try:
#         _send_whatsapp_prompt(reg, step)
#     except Exception:
#         logger.exception(f"[ERROR] Failed to send WA prompt for step={step}")
#         # Do NOT advance; let the next WAKE try again
#         return

#     # Only if send succeeded do we record that we prompted this step
#     sess.step = step
#     sess.last_prompt_step = step
#     sess.last_msg_at = dj_tz.now()
#     sess.save(update_fields=["step", "last_prompt_step", "last_msg_at"])


# @transaction.atomic
# def apply_button_choice(reg: EventRegistration, step: str, raw_value: str) -> None:
#     """
#     Applies a button value to the appropriate TravelDetail field and advances to the next prompt.
#     """
#     td = _get_or_create_detail(reg)
#     sess = _get_or_create_session(reg)

#     try:
#         if step == "travel_type" and raw_value in TRAVEL_TYPE_CHOICES:
#             td.travel_type = raw_value
#             td.save(update_fields=["travel_type"])

#         elif step == "arrival" and raw_value in ARRIVAL_CHOICES:
#             td.arrival = raw_value
#             td.save(update_fields=["arrival"])

#         elif step == "return_travel":
#             # mark answered in state, and store boolean in td
#             sess.state = sess.state or {}
#             sess.state["return_travel_done"] = True
#             td.return_travel = raw_value == "yes"
#             td.save(update_fields=["return_travel"])
#             sess.save(update_fields=["state"])

#         elif step == "departure" and raw_value in ARRIVAL_CHOICES:
#             td.departure = raw_value
#             td.save(update_fields=["departure"])

#         else:
#             logger.warning(
#                 f"[BUTTON] Unknown or invalid step/value: step={step!r} value={raw_value!r}"
#             )
#     except Exception:
#         logger.exception(f"[ERROR] Failed to apply button choice for step={step}")
#         return

#     # After applying choice, move to next step
#     try:
#         send_next_prompt(reg)
#     except Exception:
#         logger.exception("[ERROR] Failed in send_next_prompt after button choice")


# @transaction.atomic
# def handle_inbound_answer(reg: EventRegistration, text: str) -> Tuple[str, bool]:
#     """
#     Handles typed (free-text) answers for non-choice steps.
#     Returns (reply_text, completed_flag).
#     """
#     sess = _get_or_create_session(reg)
#     td = _get_or_create_detail(reg)

#     if sess.step in {"opt_in", ""}:
#         sess.step = "travel_type"

#     step = sess.step or "travel_type"
#     t = (text or "").strip()
#     logger.warning(f"[ANSWER] step={step!r} text={t!r}")

#     state_changed = False

#     try:
#         if step == "travel_type":
#             val = _choice(t, TRAVEL_TYPE_CHOICES)
#             if not val:
#                 return ("Please tap a button or reply: Air / Train / Car", False)
#             td.travel_type = val
#             td.save(update_fields=["travel_type"])

#         elif step == "arrival":
#             val = _choice(t, ARRIVAL_CHOICES)
#             if not val:
#                 return (
#                     "Please tap a button or reply: Commercial / Local Pickup / Self",
#                     False,
#                 )
#             td.arrival = val
#             td.save(update_fields=["arrival"])

#         elif step == "arrival_date":
#             dt = _parse_date(t)
#             if not dt:
#                 return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
#             td.arrival_date = dt
#             td.save(update_fields=["arrival_date"])

#         elif step == "arrival_time":
#             tm = _parse_time(t)
#             if not tm:
#                 return ("Please send time like 14:30 or 2:30pm.", False)
#             td.arrival_time = tm
#             td.save(update_fields=["arrival_time"])

#         elif step == "airline":
#             td.airline = t
#             td.save(update_fields=["airline"])

#         elif step == "flight_number":
#             td.flight_number = t.upper()
#             td.save(update_fields=["flight_number"])

#         elif step == "pnr":
#             td.pnr = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["pnr_done"] = True
#             state_changed = True
#             td.save(update_fields=["pnr"])

#         elif step == "arrival_details":
#             td.arrival_details = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["arrival_details_done"] = True
#             state_changed = True
#             td.save(update_fields=["arrival_details"])

#         elif step == "hotel_arrival_time":
#             key = t.strip().lower()
#             sess.state = sess.state or {}
#             if key in {"skip", "none", "na", "n/a", ""}:
#                 td.hotel_arrival_time = None
#                 sess.state["hat_skip"] = True
#             else:
#                 tm = _parse_time(t)
#                 if not tm:
#                     return ("Time looks off. Example: 13:45", False)
#                 td.hotel_arrival_time = tm
#                 sess.state.pop("hat_skip", None)
#             state_changed = True
#             td.save(update_fields=["hotel_arrival_time"])

#         elif step == "hotel_departure_time":
#             key = t.strip().lower()
#             sess.state = sess.state or {}
#             if key in {"skip", "none", "na", "n/a", ""}:
#                 td.hotel_departure_time = None
#                 sess.state["hdt_skip"] = True
#             else:
#                 tm = _parse_time(t)
#                 if not tm:
#                     return ("Time looks off. Example: 10:00", False)
#                 td.hotel_departure_time = tm
#                 sess.state.pop("hdt_skip", None)
#             state_changed = True
#             td.save(update_fields=["hotel_departure_time"])

#         elif step == "return_travel":
#             b = _yn(t)
#             if b is None:
#                 return ("Please tap Yes/No.", False)
#             td.return_travel = b
#             sess.state = sess.state or {}
#             sess.state["return_travel_done"] = True
#             state_changed = True
#             td.save(update_fields=["return_travel"])

#         elif step == "departure":
#             val = _choice(t, ARRIVAL_CHOICES)
#             if not val:
#                 return (
#                     "Please tap a button or reply: Commercial / Local Pickup / Self",
#                     False,
#                 )
#             td.departure = val
#             td.save(update_fields=["departure"])

#         elif step == "departure_date":
#             dt = _parse_date(t)
#             if not dt:
#                 return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
#             td.departure_date = dt
#             td.save(update_fields=["departure_date"])

#         elif step == "departure_time":
#             tm = _parse_time(t)
#             if not tm:
#                 return ("Send time like 18:20 or 6:20pm", False)
#             td.departure_time = tm
#             td.save(update_fields=["departure_time"])

#         elif step == "departure_airline":
#             td.departure_airline = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["departure_airline_done"] = True
#             state_changed = True
#             td.save(update_fields=["departure_airline"])

#         elif step == "departure_flight_number":
#             td.departure_flight_number = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["departure_flight_number_done"] = True
#             state_changed = True
#             td.save(update_fields=["departure_flight_number"])

#         elif step == "departure_pnr":
#             td.departure_pnr = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["departure_pnr_done"] = True
#             state_changed = True
#             td.save(update_fields=["departure_pnr"])

#         elif step == "departure_details":
#             td.departure_details = _set_optional_text(t)
#             sess.state = sess.state or {}
#             sess.state["departure_details_done"] = True
#             state_changed = True
#             td.save(update_fields=["departure_details"])

#         else:
#             logger.warning(f"[ANSWER] Unknown step={step!r}, text={t!r}")
#             return ("Sorry, I didn't understand that. Please try again.", False)

#     except Exception:
#         logger.exception(f"[ERROR] Failed while handling inbound answer at step={step}")
#         return (
#             "Something went wrong while saving your answer. Please try again.",
#             False,
#         )

#     # advance
#     sess.step = _next_step(sess, td) or "done"
#     sess.last_msg_at = dj_tz.now()
#     if sess.step == "done":
#         sess.is_complete = True

#     if state_changed:
#         # save step + state
#         try:
#             sess.save(update_fields=["step", "last_msg_at", "is_complete", "state"])
#         except Exception:
#             logger.exception("[ERROR] Failed to save session after inbound answer")
#     else:
#         try:
#             sess.save(update_fields=["step", "last_msg_at", "is_complete"])
#         except Exception:
#             logger.exception(
#                 "[ERROR] Failed to save session after inbound answer (no state change)"
#             )

#     done = sess.step == "done"
#     if done:
#         return (PROMPTS["done"], True)
#     return (PROMPTS.get(sess.step, "OK."), False)


# """
# Conversation orchestrator for capturing TravelDetail via WhatsApp.

# Responsibilities:
# - Decide next question (step) based on TravelDetail fields and session state.
# - Send buttons for choice steps; text prompts for free-form steps.
# - Parse + validate answers; write to TravelDetail; auto-advance.
# - Resume from where the guest left off; avoid resending the same prompt.

# Choice steps use button IDs like: "tc|<step>|<value>"
# """

# import re
# from datetime import datetime, time
# from typing import Tuple, Optional, Dict, Any

# from django.utils import timezone as dj_tz
# from django.db import transaction

# from Logistics.models.travel_details_models import TravelDetail
# from Logistics.models.travel_detail_capture_session import TravelCaptureSession
# from Events.models.event_registration_model import EventRegistration
# from MessageTemplates.services.whatsapp import (
#     send_freeform_text,
#     send_choice_buttons,
# )

# # ---------- parsing helpers ----------
# _date_rx = re.compile(r"^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*$")
# _time_rx = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", re.I)


# def _parse_date(s: str):
#     m = _date_rx.match(s or "")
#     if not m:
#         return None
#     d, mo, y = map(int, m.groups())
#     try:
#         return datetime(y, mo, d).date()
#     except ValueError:
#         return None


# def _parse_time(s: str):
#     m = _time_rx.match(s or "")
#     if not m:
#         return None
#     hh, mm, ap = m.groups()
#     hh, mm = int(hh), int(mm)
#     if ap:
#         ap = ap.lower()
#         if ap == "pm" and hh < 12:
#             hh += 12
#         if ap == "am" and hh == 12:
#             hh = 0
#     if 0 <= hh <= 23 and 0 <= mm <= 59:
#         return time(hh, mm)
#     return None


# def _yn(s: str) -> Optional[bool]:
#     x = (s or "").strip().lower()
#     if x in {"y", "yes", "yeah", "yup", "true"}:
#         return True
#     if x in {"n", "no", "nope", "false"}:
#         return False
#     return None


# def _choice(s: str, choices: Dict[str, str]) -> Optional[str]:
#     x = (s or "").strip().lower()
#     for key in choices:
#         if x == key.lower():
#             return key
#     return None


# def _set_optional_text(v: str) -> Optional[str]:
#     if not v:
#         return None
#     if v.strip().lower() in {"skip", "none", "na"}:
#         return ""
#     return v.strip()


# # ---------- constants ----------
# ARRIVAL_CHOICES = {
#     "commercial": "Commercial",
#     "local_pickup": "Local Pickup",
#     "self": "Self",
# }
# TRAVEL_TYPE_CHOICES = {"Air": "Air", "Train": "Train", "Car": "Car"}

# PROMPTS = {
#     "travel_type": "How are you traveling?",
#     "arrival": "How will you arrive?",
#     "arrival_date": "What is your arrival date? Reply like 03-10-2025",
#     "arrival_time": "What is your arrival time? Reply like 14:30 or 2:30pm",
#     "airline": "What is the airline?",
#     "flight_number": "What is your flight number?",
#     "pnr": "What is your PNR? (optional, reply 'skip' to skip)",
#     "arrival_details": "Any arrival details we should know (pickup location, notes)? (reply 'skip' to skip)",
#     "hotel_arrival_time": "What time will you reach the hotel? (HH:MM, or 'skip')",
#     "hotel_departure_time": "What time will you depart the hotel? (HH:MM, or 'skip')",
#     "return_travel": "Do you have a return journey?",
#     "departure": "How will you depart?",
#     "departure_date": "What is your departure date? (DD-MM-YYYY)",
#     "departure_time": "What is your departure time? (HH:MM)",
#     "departure_airline": "Departure airline? (if applicable; or 'skip')",
#     "departure_flight_number": "Departure flight/train number? (or 'skip')",
#     "departure_pnr": "Departure PNR? (or 'skip')",
#     "departure_details": "Any departure details (pickup spot/notes)? (or 'skip')",
#     "done": "Thanks! We’ve recorded your travel details. You can reply later to update a field (e.g., 'change airline Indigo').",
# }


# # ---------- session/detail helpers ----------
# def _get_or_create_session(reg: EventRegistration) -> TravelCaptureSession:
#     sess, _ = TravelCaptureSession.objects.get_or_create(registration=reg)
#     return sess


# def _get_or_create_detail(reg: EventRegistration) -> TravelDetail:
#     td = TravelDetail.objects.filter(event=reg.event, event_registrations=reg).first()
#     if td:
#         return td
#     td = TravelDetail.objects.create(event=reg.event)
#     td.event_registrations.add(reg)
#     return td


# # ---------- next step logic ----------
# def _next_step(sess: TravelCaptureSession, td: TravelDetail) -> Optional[str]:
#     if sess.step == "done":
#         return None

#     pending = []

#     # core
#     if not td.travel_type:
#         pending.append("travel_type")
#     if not td.arrival:
#         pending.append("arrival")
#     if not td.arrival_date:
#         pending.append("arrival_date")
#     if not td.arrival_time:
#         pending.append("arrival_time")

#     # commercial air specifics
#     if td.travel_type == "Air" and td.arrival == "commercial":
#         if not td.airline:
#             pending.append("airline")
#         if not td.flight_number:
#             pending.append("flight_number")
#         if td.pnr is None:
#             pending.append("pnr")

#     # optional arrival note, hotel times
#     if td.arrival_details is None:
#         pending.append("arrival_details")
#     if td.hotel_arrival_time is None:
#         pending.append("hotel_arrival_time")
#     if td.hotel_departure_time is None:
#         pending.append("hotel_departure_time")

#     # return branch
#     if td.return_travel is False and "return_travel" not in (sess.state or {}):
#         pending.append("return_travel")
#     elif td.return_travel is True:
#         if not td.departure:
#             pending.append("departure")
#         if not td.departure_date:
#             pending.append("departure_date")
#         if not td.departure_time:
#             pending.append("departure_time")
#         if td.travel_type == "Air" and td.departure == "commercial":
#             if td.departure_airline is None:
#                 pending.append("departure_airline")
#             if td.departure_flight_number is None:
#                 pending.append("departure_flight_number")
#             if td.departure_pnr is None:
#                 pending.append("departure_pnr")
#         if td.departure_details is None:
#             pending.append("departure_details")

#     if not pending:
#         return "done"
#     return pending[0]


# # ---------- public API ----------
# def start_capture_after_opt_in(reg: EventRegistration, *, restart: bool = False) -> str:
#     sess = _get_or_create_session(reg)
#     _get_or_create_detail(reg)

#     if restart or sess.is_complete:
#         sess.step = "travel_type"
#         sess.is_complete = False
#         sess.state = {}
#     else:
#         sess.step = sess.step or "travel_type"

#     sess.last_msg_at = dj_tz.now()
#     sess.save(update_fields=["step", "is_complete", "state", "last_msg_at"])

#     # Immediately fire first pending question
#     send_next_prompt(reg)

#     return sess.step


# def resume_or_start(reg: EventRegistration) -> None:
#     """Resume from saved step or start at 'travel_type' and send the appropriate next prompt."""
#     sess = _get_or_create_session(reg)
#     if not sess.step or sess.step in {"opt_in", ""}:
#         start_capture_after_opt_in(reg, restart=False)
#     send_next_prompt(reg)


# def send_next_prompt(reg: EventRegistration) -> None:
#     """
#     Chooses buttons for choice steps; otherwise sends text prompt.
#     Uses last_prompt_step to avoid repeating the same question accidentally.
#     """
#     sess = _get_or_create_session(reg)
#     td = _get_or_create_detail(reg)

#     step = _next_step(sess, td) if sess.step != "done" else None
#     if not step or step == "done":
#         send_freeform_text(reg.guest.phone, PROMPTS["done"])
#         sess.step = "done"
#         sess.is_complete = True
#         sess.last_prompt_step = "done"
#         sess.last_msg_at = dj_tz.now()
#         sess.save(
#             update_fields=["step", "is_complete", "last_prompt_step", "last_msg_at"]
#         )
#         return

#     if sess.last_prompt_step == step:
#         # Avoid resending the exact same prompt.
#         return

#     sess.step = step
#     sess.last_prompt_step = step
#     sess.last_msg_at = dj_tz.now()
#     sess.save(update_fields=["step", "last_prompt_step", "last_msg_at"])

#     # Buttons for choice steps
#     if step == "travel_type":
#         send_choice_buttons(
#             reg.guest.phone,
#             "How are you traveling?",
#             [
#                 {"id": "tc|travel_type|Air", "title": "Air"},
#                 {"id": "tc|travel_type|Train", "title": "Train"},
#                 {"id": "tc|travel_type|Car", "title": "Car"},
#             ],
#         )
#         return
#     if step == "arrival":
#         send_choice_buttons(
#             reg.guest.phone,
#             "How will you arrive?",
#             [
#                 {"id": "tc|arrival|commercial", "title": "Commercial"},
#                 {"id": "tc|arrival|local_pickup", "title": "Local Pickup"},
#                 {"id": "tc|arrival|self", "title": "Self"},
#             ],
#         )
#         return
#     if step == "return_travel":
#         send_choice_buttons(
#             reg.guest.phone,
#             "Do you have a return journey?",
#             [
#                 {"id": "tc|return_travel|yes", "title": "Yes"},
#                 {"id": "tc|return_travel|no", "title": "No"},
#             ],
#         )
#         return
#     if step == "departure":
#         send_choice_buttons(
#             reg.guest.phone,
#             "How will you depart?",
#             [
#                 {"id": "tc|departure|commercial", "title": "Commercial"},
#                 {"id": "tc|departure|local_pickup", "title": "Local Pickup"},
#                 {"id": "tc|departure|self", "title": "Self"},
#             ],
#         )
#         return

#     # Free-form prompts for the rest
#     send_freeform_text(reg.guest.phone, PROMPTS.get(step, "OK."))


# @transaction.atomic
# def apply_button_choice(reg: EventRegistration, step: str, raw_value: str) -> None:
#     """
#     Applies a button value to the appropriate TravelDetail field and advances to the next prompt.
#     """
#     td = _get_or_create_detail(reg)
#     sess = _get_or_create_session(reg)

#     if step == "travel_type" and raw_value in TRAVEL_TYPE_CHOICES:
#         td.travel_type = raw_value
#         td.save(update_fields=["travel_type"])
#     elif step == "arrival" and raw_value in ARRIVAL_CHOICES:
#         td.arrival = raw_value
#         td.save(update_fields=["arrival"])
#     elif step == "return_travel":
#         td.return_travel = raw_value == "yes"
#         td.save(update_fields=["return_travel"])
#         sess.state["return_travel"] = td.return_travel
#     elif step == "departure" and raw_value in ARRIVAL_CHOICES:
#         td.departure = raw_value
#         td.save(update_fields=["departure"])

#     send_next_prompt(reg)


# @transaction.atomic
# def handle_inbound_answer(reg: EventRegistration, text: str) -> Tuple[str, bool]:
#     """
#     Handles typed (free-text) answers for non-choice steps.
#     Returns (reply_text, completed_flag).
#     """
#     sess = _get_or_create_session(reg)
#     td = _get_or_create_detail(reg)

#     if sess.step in {"opt_in", ""}:
#         sess.step = "travel_type"

#     step = sess.step or "travel_type"
#     t = (text or "").strip()

#     if step == "travel_type":
#         val = _choice(t, TRAVEL_TYPE_CHOICES)
#         if not val:
#             return ("Please tap a button or reply: Air / Train / Car", False)
#         td.travel_type = val
#         td.save(update_fields=["travel_type"])

#     elif step == "arrival":
#         val = _choice(t, ARRIVAL_CHOICES)
#         if not val:
#             return (
#                 "Please tap a button or reply: commercial / local_pickup / self",
#                 False,
#             )
#         td.arrival = val
#         td.save(update_fields=["arrival"])

#     elif step == "arrival_date":
#         dt = _parse_date(t)
#         if not dt:
#             return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
#         td.arrival_date = dt
#         td.save(update_fields=["arrival_date"])

#     elif step == "arrival_time":
#         tm = _parse_time(t)
#         if not tm:
#             return ("Please send time like 14:30 or 2:30pm.", False)
#         td.arrival_time = tm
#         td.save(update_fields=["arrival_time"])

#     elif step == "airline":
#         td.airline = t
#         td.save(update_fields=["airline"])

#     elif step == "flight_number":
#         td.flight_number = t.upper()
#         td.save(update_fields=["flight_number"])

#     elif step == "pnr":
#         td.pnr = _set_optional_text(t)
#         td.save(update_fields=["pnr"])

#     elif step == "arrival_details":
#         td.arrival_details = _set_optional_text(t)
#         td.save(update_fields=["arrival_details"])

#     elif step == "hotel_arrival_time":
#         if t.strip().lower() in {"skip", ""}:
#             td.hotel_arrival_time = None
#         else:
#             tm = _parse_time(t)
#             if not tm:
#                 return ("Time looks off. Example: 13:45", False)
#             td.hotel_arrival_time = tm
#         td.save(update_fields=["hotel_arrival_time"])

#     elif step == "hotel_departure_time":
#         if t.strip().lower() in {"skip", ""}:
#             td.hotel_departure_time = None
#         else:
#             tm = _parse_time(t)
#             if not tm:
#                 return ("Time looks off. Example: 10:00", False)
#             td.hotel_departure_time = tm
#         td.save(update_fields=["hotel_departure_time"])

#     elif step == "return_travel":
#         b = _yn(t)
#         if b is None:
#             return ("Please tap Yes/No.", False)
#         td.return_travel = b
#         td.save(update_fields=["return_travel"])
#         sess.state["return_travel"] = b

#     elif step == "departure":
#         val = _choice(t, ARRIVAL_CHOICES)
#         if not val:
#             return (
#                 "Please tap a button or reply: commercial / local_pickup / self",
#                 False,
#             )
#         td.departure = val
#         td.save(update_fields=["departure"])

#     elif step == "departure_date":
#         dt = _parse_date(t)
#         if not dt:
#             return ("Please send date as DD-MM-YYYY (e.g., 03-10-2025).", False)
#         td.departure_date = dt
#         td.save(update_fields=["departure_date"])

#     elif step == "departure_time":
#         tm = _parse_time(t)
#         if not tm:
#             return ("Send time like 18:20 or 6:20pm", False)
#         td.departure_time = tm
#         td.save(update_fields=["departure_time"])

#     elif step == "departure_airline":
#         td.departure_airline = _set_optional_text(t)
#         td.save(update_fields=["departure_airline"])

#     elif step == "departure_flight_number":
#         td.departure_flight_number = _set_optional_text(t)
#         td.save(update_fields=["departure_flight_number"])

#     elif step == "departure_pnr":
#         td.departure_pnr = _set_optional_text(t)
#         td.save(update_fields=["departure_pnr"])

#     elif step == "departure_details":
#         td.departure_details = _set_optional_text(t)
#         td.save(update_fields=["departure_details"])

#     # advance
#     sess.step = _next_step(sess, td) or "done"
#     sess.last_msg_at = dj_tz.now()
#     if sess.step == "done":
#         sess.is_complete = True
#     sess.last_prompt_step = sess.step
#     sess.save(update_fields=["step", "last_msg_at", "is_complete", "last_prompt_step"])

#     done = sess.step == "done"
#     if done:
#         return (PROMPTS["done"], True)
#     return (PROMPTS.get(sess.step, "OK."), False)
