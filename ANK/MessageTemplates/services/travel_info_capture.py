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
import requests
import os
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


def _validate_optional_pnr(v: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validates PNR input. Returns (value, error_message).
    - If skip keyword: returns ("", None)
    - If valid PNR: returns (pnr, None)
    - If invalid: returns (None, error_message)
    """
    if v is None:
        return "", None
    s = v.strip()
    if not s:
        return "", None
    sl = s.lower()
    if sl in {"skip", "none", "na", "n/a", "-"}:
        return "", None
    
    # PNR should be alphanumeric and have reasonable length (typically 4-10 chars)
    if len(s) < 3:
        return None, (
            f"I couldn't understand '{s}' as a valid PNR. 🤔\n\n"
            "PNR is usually a combination of letters and numbers (e.g., ABC123, XYZ456).\n\n"
            "Please reply with:\n"
            "• Your PNR code, OR\n"
            "• *skip* if you don't have it right now"
        )
    
    if not s.replace(" ", "").replace("-", "").isalnum():
        return None, (
            f"I couldn't understand '{s}' as a valid PNR. 🤔\n\n"
            "PNR should contain only letters and numbers.\n\n"
            "Please reply with:\n"
            "• Your PNR code (e.g., ABC123), OR\n"
            "• *skip* if you don't have it right now"
        )
    
    return s.upper(), None


def _validate_optional_text(v: str, field_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validates optional text input. Returns (value, error_message).
    - If skip keyword: returns ("", None)
    - If valid text: returns (text, None)
    - If invalid (too short/garbage): returns (None, error_message)
    """
    if v is None:
        return "", None
    s = v.strip()
    if not s:
        return "", None
    sl = s.lower()
    if sl in {"skip", "none", "na", "n/a", "-"}:
        return "", None
    
    # Reject single character or very short inputs that look like garbage
    if len(s) < 2:
        return None, (
            f"I couldn't understand '{s}'. 🤔\n\n"
            f"Please provide more details for {field_name}, or reply *skip* if you don't have any."
        )
    
    return s, None


# ---------- constants ----------

ARRIVAL_CHOICES = {
    "commercial": "Commercial",
    "local_pickup": "Local Pickup",
    "self": "Self",
}
TRAVEL_TYPE_CHOICES = {"Air": "Air", "Train": "Train", "Car": "Car"}

# Steps that should always be rendered as WhatsApp buttons
CHOICE_STEPS = {"travel_type", "arrival", "return_travel", "departure", "extra_attendees_count"}

# Optional steps that can be skipped - will show a Skip button
OPTIONAL_STEPS = {
    "pnr", "arrival_details", "hotel_arrival_time", "hotel_departure_time",
    "departure_airline", "departure_flight_number", "departure_pnr", "departure_details"
}

PROMPTS = {
    "travel_type": "How will you be traveling to the event? ✈️🚆🚗",
    "arrival": "Great! How will you be arriving at the venue?",
    "arrival_date": "📅 ➡️ ARRIVAL: What's your *Arrival Date*? Please reply in DD-MM-YYYY format (e.g., 03-10-2025).",
    "arrival_time": "🕒 🛬 What time will you be arriving? (e.g., 14:30 or 2:30pm)",
    "airline": "Which *Airline* are you flying with? ✈️",
    "flight_number": "Could you share the *Flight Number*?",
    "pnr": "Do you have the *PNR* handy? (Reply 'skip' if you don't have it right now)",
    "arrival_details": "📝 ➡️ Any other arrival details we should know? (e.g., pickup location, special requirements)",
    "hotel_arrival_time": "🏨 ⬇️ CHECK-IN: What time do you expect to *arrive at the hotel*? (e.g., 15:00 or 3pm)",
    "hotel_departure_time": "🏨 ⬆️ CHECK-OUT: What time will you be *leaving the hotel*? (e.g., 11:00 or 11am)",
    "return_travel": "Do you have a return journey planned? 🔙",
    "departure": "How will you be departing?",
    "departure_date": "📅 ⬅️ RETURN: What's your *Departure Date*? (DD-MM-YYYY format)",
    "departure_time": "🕒 🛫 What time is your departure? (e.g., 18:30 or 6:30pm)",
    "departure_details": "📝 ⬅️ Any departure details we should know? (e.g., drop-off location, notes)",
    "done": "Perfect! We've saved your travel details. ✅\n\nIf you need to update anything:\n• Reply *rsvp* to change your RSVP status\n• Reply *travel* to update travel details\n\nSafe travels! 🌟",
}


def _get_prompt_text(step: str, travel_type: str = "Air") -> str:
    """
    Returns dynamic prompt text based on travel_type.
    """
    tt = (travel_type or "Air").lower()

    if step == "airline":
        if tt == "train":
            return "Which *Train* are you taking? 🚆"
        if tt == "car":
            return "Which *Car Company* is providing the service? 🚗"
        return "Which *Airline* are you flying with? ✈️"

    if step == "flight_number":
        if tt == "train":
            return "Could you share the *Train Number*?"
        if tt == "car":
            return "Could you share the *Car Number*?"
        return "Could you share the *Flight Number*?"

    if step == "pnr":
        if tt == "train":
            return "Do you have the *PNR*? (Reply 'skip' if not available)"
        if tt == "car":
            return "Do you have the *Driver Number*? (Reply 'skip' if not available)"
        return "Do you have the *PNR* handy? (Reply 'skip' if you don't have it right now)"

    # Departure variants
    if step == "departure_airline":
        if tt == "train":
            return "🚆 ⬅️ RETURN JOURNEY: Which *Train* are you taking back?"
        if tt == "car":
            return "🚗 ⬅️ RETURN JOURNEY: Which *Car Company* for the return trip?"
        return "✈️ ⬅️ RETURN JOURNEY: Which *Airline* are you flying back with?"

    if step == "departure_flight_number":
        if tt == "train":
            return "🚆 ⬅️ What's your return *Train Number*?"
        if tt == "car":
            return "🚗 ⬅️ What's your return *Car Number* or booking reference?"
        return "✈️ ⬅️ What's your return *Flight Number*?"

    if step == "departure_pnr":
        if tt == "train":
            return "🚆 ⬅️ Do you have the return journey *PNR*?"
        if tt == "car":
            return "🚗 ⬅️ Do you have the *Driver Number* for the return trip?"
        return "✈️ ⬅️ Do you have the return flight *PNR*?"

    return PROMPTS.get(step, "OK.")


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
    # Create with default arrival and departure set to 'commercial'
    td = TravelDetail.objects.create(
        event=reg.event,
        arrival="commercial",
        departure="commercial"
    )
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
    reg = sess.registration

    # --- core arrival stuff ---
    if not td.travel_type:
        pending.append("travel_type")
    
    # --- Extra Guests Check ---
    # Ask this immediately after travel type
    if td.travel_type and not state.get("extra_attendees_count_done"):
        # Only ask if they actually have extra attendees
        if reg.extra_attendees.exists():
            pending.append("extra_attendees_count")
        else:
            # Auto-mark as done if no extras
            state["extra_attendees_count_done"] = True
            state["extra_attendees_count"] = 0
            # Ensure state is assigned back to session before saving
            sess.state = state
            sess.save(update_fields=["state"])

    # SKIP arrival question - default to 'commercial'
    if not td.arrival_date:
        pending.append("arrival_date")
    if not td.arrival_time:
        pending.append("arrival_time")

    # --- inbound commercial air specifics ---
    # --- inbound carrier specifics (Air/Train/Car) ---
    if td.travel_type:
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
        # SKIP departure question - default to 'commercial'
        if not td.departure_date:
            pending.append("departure_date")
        if not td.departure_time:
            pending.append("departure_time")

        # Departure details for return journey
        if td.departure:
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

    if step == "extra_attendees_count":
        total_extras = reg.extra_attendees.count()
        buttons = []
        # Offer buttons for 0 up to min(total, 2) to keep it simple, or maybe up to 3
        # WhatsApp allows max 3 buttons usually in some templates, but list messages allow more.
        # send_choice_buttons uses interactive buttons (max 3).
        
        # If they have 1 extra: [0, 1]
        # If they have 2 extras: [0, 1, 2]
        # If they have 3+ extras: [0, All(N), Type] -> actually let's just give common options
        
        if total_extras == 1:
            buttons = [
                {"id": "tc|extra_attendees_count|1", "title": "Yes, 1 Guest"},
                {"id": "tc|extra_attendees_count|0", "title": "No, just me"},
            ]
        else:
            buttons.append({"id": f"tc|extra_attendees_count|{total_extras}", "title": f"All {total_extras} Guests"})
            if total_extras > 1:
                buttons.append({"id": "tc|extra_attendees_count|0", "title": "Just me"})
            # Add a 'Type' option? Or just let them type. 
            # If we have space for a 3rd button and total > 1, maybe "Some..."?
            # For now, let's stick to "All" and "Just me" as quick options. 
            # If they want a specific number, they can type it (we'll mention it in text).
        
        msg = (
            f"You have {total_extras} extra guests registered with you. 👥\n\n"
            "How many of them are traveling with you on this journey?"
        )
        
        send_choice_buttons(phone, msg, buttons)
        return

    # Optional steps with Skip button
    if step in OPTIONAL_STEPS:
        td = _get_or_create_detail(reg)
        text = _get_prompt_text(step, td.travel_type)
        send_choice_buttons(
            phone,
            text,
            [{"id": f"tc|{step}|__skip__", "title": "⏭️ Skip"}],
        )
        return

    # Free-form for the rest
    # Use dynamic prompt text
    td = _get_or_create_detail(reg)
    text = _get_prompt_text(step, td.travel_type)
    send_freeform_text(phone, text)


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
        
        # --- POST-COMPLETION ACTIONS ---
        # Link extra attendees if count > 0
        try:
            count = (sess.state or {}).get("extra_attendees_count", 0)
            if count > 0:
                extras = list(reg.extra_attendees.all()[:count])
                if extras:
                    td.extra_attendees.add(*extras)
                    logger.warning(f"[DONE] Linked {len(extras)} extra attendees to TravelDetail {td.id}")
        except Exception as exc:
            logger.exception(f"[DONE-ERR] Failed to link extra attendees: {exc}")
            
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
        # Handle skip button for optional fields
        if raw_value == "__skip__" and step in OPTIONAL_STEPS:
            sess.state = sess.state or {}
            # Mark the field as done (skipped)
            if step == "pnr":
                td.pnr = ""
                sess.state["pnr_done"] = True
                td.save(update_fields=["pnr"])
            elif step == "arrival_details":
                td.arrival_details = ""
                sess.state["arrival_details_done"] = True
                td.save(update_fields=["arrival_details"])
            elif step == "hotel_arrival_time":
                td.hotel_arrival_time = None
                sess.state["hat_skip"] = True
                td.save(update_fields=["hotel_arrival_time"])
            elif step == "hotel_departure_time":
                td.hotel_departure_time = None
                sess.state["hdt_skip"] = True
                td.save(update_fields=["hotel_departure_time"])
            elif step == "departure_airline":
                td.departure_airline = ""
                sess.state["departure_airline_done"] = True
                td.save(update_fields=["departure_airline"])
            elif step == "departure_flight_number":
                td.departure_flight_number = ""
                sess.state["departure_flight_number_done"] = True
                td.save(update_fields=["departure_flight_number"])
            elif step == "departure_pnr":
                td.departure_pnr = ""
                sess.state["departure_pnr_done"] = True
                td.save(update_fields=["departure_pnr"])
            elif step == "departure_details":
                td.departure_details = ""
                sess.state["departure_details_done"] = True
                td.save(update_fields=["departure_details"])
            sess.save(update_fields=["state"])

        elif step == "travel_type" and raw_value in TRAVEL_TYPE_CHOICES:
            # If changing type, reset arrival + air fields to force re-ask
            if td.travel_type != raw_value:
                td.travel_type = raw_value
                td.arrival = None
                td.airline = ""
                td.flight_number = ""
                td.pnr = ""
                # Clear PNR state if any
                sess.state = sess.state or {}
                sess.state.pop("pnr_done", None)
                sess.save(update_fields=["state"])
                
                td.save(update_fields=["travel_type", "arrival", "airline", "flight_number", "pnr"])
            else:
                td.save(update_fields=["travel_type"])

        elif step == "arrival" and raw_value in ARRIVAL_CHOICES:
            # If changing arrival, check if we need to clear air fields
            if td.arrival != raw_value:
                td.arrival = raw_value
                # If switching away from commercial, clear air fields
                if raw_value != "commercial":
                    td.airline = ""
                    td.flight_number = ""
                    td.pnr = ""
                    sess.state = sess.state or {}
                    sess.state.pop("pnr_done", None)
                    sess.save(update_fields=["state"])
                    td.save(update_fields=["arrival", "airline", "flight_number", "pnr"])
                else:
                    # Switching TO commercial: clear fields to be safe so we don't skip steps.
                    td.airline = ""
                    td.flight_number = ""
                    td.pnr = ""
                    sess.state = sess.state or {}
                    sess.state.pop("pnr_done", None)
                    sess.save(update_fields=["state"])
                    td.save(update_fields=["arrival", "airline", "flight_number", "pnr"])
            else:
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
            
        elif step == "extra_attendees_count":
            try:
                count = int(raw_value)
                sess.state = sess.state or {}
                sess.state["extra_attendees_count"] = count
                sess.state["extra_attendees_count_done"] = True
                sess.save(update_fields=["state"])
            except ValueError:
                pass



        elif step.startswith("rsvp_"):
            status = step.replace("rsvp_", "")
            if status in ["yes", "no", "maybe"]:
                # Call existing RSVP webhook to trigger WebSocket broadcasts
                try:
                    # We use localhost because we are calling our own API
                    webhook_url = "http://127.0.0.1:8000/api/webhooks/whatsapp-rsvp/"
                    response = requests.post(
                        webhook_url,
                        json={
                            "rsvp_status": status,
                            "event_registration_id": str(reg.id),
                            "responded_on": dj_tz.now().isoformat()
                        },
                        headers={"X-Webhook-Token": os.getenv("DJANGO_RSVP_SECRET", "")},
                        timeout=5
                    )
                    if response.status_code != 200:
                        logger.error(f"[RSVP-BUTTON] Webhook returned {response.status_code}")
                except Exception as exc:
                    logger.exception(f"[RSVP-BUTTON] Failed to call webhook: {exc}")

                # Send appropriate response based on status
                if status == "yes":
                    # Ask for guest count
                    try:
                        send_freeform_text(
                            reg.guest.phone,
                            "Great! How many people will be attending (including you)? 👥\n\n"
                            "Please reply with a number (e.g., 2, 3, 4)"
                        )
                        # Set flag to expect guest count
                        sess.state = sess.state or {}
                        sess.state["awaiting_guest_count"] = True
                        sess.save(update_fields=["state"])
                    except Exception as exc:
                        logger.exception(f"[RSVP-BUTTON] Failed to send guest count prompt: {exc}")
                
                elif status == "no":
                    try:
                        send_freeform_text(
                            reg.guest.phone,
                            "Thank you for letting us know.\n\n"
                            "Your RSVP has been updated to: Not Attending ❌\n\n"
                            "We hope to see you at future events!"
                        )
                    except Exception as exc:
                        logger.exception(f"[RSVP-BUTTON] Failed to send decline confirmation: {exc}")
                
                elif status == "maybe":
                    try:
                        send_freeform_text(
                            reg.guest.phone,
                            "No problem! Your RSVP has been updated to: Maybe 🤔\n\n"
                            "Please let us know when you decide!"
                        )
                    except Exception as exc:
                        logger.exception(f"[RSVP-BUTTON] Failed to send maybe confirmation: {exc}")
            return

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
                return (
                    f"I didn't understand '{t}' as a travel type. 🤔\n\n"
                    "Please choose one of these options:\n"
                    "• Tap a button above, OR\n"
                    "• Reply with: *Air*, *Train*, or *Car*",
                    False
                )
            td.travel_type = val
            td.save(update_fields=["travel_type"])

        elif step == "arrival":
            val = _choice(t, ARRIVAL_CHOICES)
            if not val:
                return (
                    f"I didn't understand '{t}' as an arrival option. 🤔\n\n"
                    "Please choose one of these:\n"
                    "• Tap a button above, OR\n"
                    "• Reply with: *Commercial*, *Local Pickup*, or *Self*",
                    False,
                )
            td.arrival = val
            td.save(update_fields=["arrival"])

        elif step == "return_travel":
            b = _yn(t)
            if b is None:
                return (
                    f"I didn't understand '{t}' as a yes/no answer. 🤔\n\n"
                    "Please let me know:\n"
                    "• Tap a button above, OR\n"
                    "• Reply with: *Yes* or *No*",
                    False
                )
            td.return_travel = b
            sess.state = sess.state or {}
            sess.state["return_travel_done"] = True
            state_changed = True
            td.save(update_fields=["return_travel"])

        elif step == "departure":
            val = _choice(t, ARRIVAL_CHOICES)
            if not val:
                return (
                    f"I didn't understand '{t}' as a departure option. 🤔\n\n"
                    "Please choose one of these:\n"
                    "• Tap a button above, OR\n"
                    "• Reply with: *Commercial*, *Local Pickup*, or *Self*",
                    False,
                )
            td.departure = val
            td.save(update_fields=["departure"])

        # --- Pure free-text / date / time steps ---
        elif step == "arrival_date":
            dt = _parse_date(t)
            if not dt:
                return (
                    f"I couldn't understand '{t}' as a valid date. 📅\n\n"
                    "Please reply with the date in *DD-MM-YYYY* format.\n\n"
                    "Examples:\n"
                    "• 03-10-2025\n"
                    "• 15/12/2025\n"
                    "• 01-01-2026",
                    False
                )
            td.arrival_date = dt
            td.save(update_fields=["arrival_date"])

        elif step == "arrival_time":
            tm = _parse_time(t)
            if not tm:
                return (
                    f"I couldn't understand '{t}' as a valid time. 🕒\n\n"
                    "Please reply with the time in one of these formats:\n\n"
                    "Examples:\n"
                    "• 14:30 (24-hour format)\n"
                    "• 2:30pm (12-hour format)\n"
                    "• 09:15am",
                    False
                )
            td.arrival_time = tm
            td.save(update_fields=["arrival_time"])

        elif step == "airline":
            td.airline = t
            td.save(update_fields=["airline"])

        elif step == "flight_number":
            td.flight_number = t.upper()
            td.save(update_fields=["flight_number"])

        # --- OPTIONAL FIELDS: Validate, then mark as done after receiving an answer ---
        elif step == "pnr":
            val, error = _validate_optional_pnr(t)
            if error:
                return (error, False)
            td.pnr = val
            sess.state = sess.state or {}
            sess.state["pnr_done"] = True
            state_changed = True
            td.save(update_fields=["pnr"])

        elif step == "arrival_details":
            val, error = _validate_optional_text(t, "arrival details")
            if error:
                return (error, False)
            td.arrival_details = val
            sess.state = sess.state or {}
            sess.state["arrival_details_done"] = True
            state_changed = True
            td.save(update_fields=["arrival_details"])

        elif step == "hotel_arrival_time":
            val = _set_optional_text(t)
            sess.state = sess.state or {}
            if not val:  # User wants to skip
                td.hotel_arrival_time = None
                sess.state["hat_skip"] = True
            else:
                tm = _parse_time(val)
                if not tm:
                    return (
                        f"I couldn't understand '{val}' as a valid time. 🕒\n\n"
                        "Please reply with the time format:\n\n"
                        "Examples:\n"
                        "• 13:45 (24-hour)\n"
                        "• 1:45pm (12-hour)\n\n"
                        "Or reply *skip* if you don't have this info yet.",
                        False
                    )
                td.hotel_arrival_time = tm
                sess.state.pop("hat_skip", None)
            state_changed = True
            td.save(update_fields=["hotel_arrival_time"])

        elif step == "hotel_departure_time":
            val = _set_optional_text(t)
            sess.state = sess.state or {}
            if not val:  # User wants to skip
                td.hotel_departure_time = None
                sess.state["hdt_skip"] = True
            else:
                tm = _parse_time(val)
                if not tm:
                    return (
                        f"I couldn't understand '{val}' as a valid time. 🕒\n\n"
                        "Please reply with the time format:\n\n"
                        "Examples:\n"
                        "• 10:00 (24-hour)\n"
                        "• 10:00am (12-hour)\n\n"
                        "Or reply *skip* if you don't have this info yet.",
                        False
                    )
                td.hotel_departure_time = tm
                sess.state.pop("hdt_skip", None)
            state_changed = True
            td.save(update_fields=["hotel_departure_time"])

        elif step == "departure_date":
            dt = _parse_date(t)
            if not dt:
                return (
                    f"I couldn't understand '{t}' as a valid date. 📅\n\n"
                    "Please reply with the date in *DD-MM-YYYY* format.\n\n"
                    "Examples:\n"
                    "• 05-10-2025\n"
                    "• 20/12/2025\n"
                    "• 03-01-2026",
                    False
                )
            td.departure_date = dt
            td.save(update_fields=["departure_date"])

        elif step == "departure_time":
            tm = _parse_time(t)
            if not tm:
                return (
                    f"I couldn't understand '{t}' as a valid time. 🕒\n\n"
                    "Please reply with the time in one of these formats:\n\n"
                    "Examples:\n"
                    "• 18:20 (24-hour format)\n"
                    "• 6:20pm (12-hour format)\n"
                    "• 11:30am",
                    False
                )
            td.departure_time = tm
            td.save(update_fields=["departure_time"])

        elif step == "departure_airline":
            val, error = _validate_optional_text(t, "airline/carrier name")
            if error:
                return (error, False)
            td.departure_airline = val
            sess.state = sess.state or {}
            sess.state["departure_airline_done"] = True
            state_changed = True
            td.save(update_fields=["departure_airline"])

        elif step == "departure_flight_number":
            val, error = _validate_optional_text(t, "flight/train/car number")
            if error:
                return (error, False)
            td.departure_flight_number = val
            sess.state = sess.state or {}
            sess.state["departure_flight_number_done"] = True
            state_changed = True
            td.save(update_fields=["departure_flight_number"])

        elif step == "departure_pnr":
            val, error = _validate_optional_pnr(t)
            if error:
                return (error, False)
            td.departure_pnr = val
            sess.state = sess.state or {}
            sess.state["departure_pnr_done"] = True
            state_changed = True
            td.save(update_fields=["departure_pnr"])

        elif step == "departure_details":
            val, error = _validate_optional_text(t, "departure details")
            if error:
                return (error, False)
            td.departure_details = val
            sess.state = sess.state or {}
            sess.state["departure_details_done"] = True
            state_changed = True
            td.save(update_fields=["departure_details"])

        else:
            logger.warning(f"[ANSWER] Unknown step={step!r}, text={t!r}")
            return (
                "Hmm, I'm not sure how to handle that response right now. 🤔\n\n"
                "Let me ask the question again - please follow the format mentioned in the prompt above.",
                False
            )

    except Exception:
        logger.exception(f"[ERROR] Failed while handling inbound answer at step={step}")
        return (
            "Something went wrong while saving your answer. Please try again.",
            False,
        )

    # Persist session meta and updated state
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

    # We successfully stored the answer -> now send whatever the *next* prompt is.
    try:
        send_next_prompt(reg)
    except Exception:
        logger.exception("[ERROR] Failed in send_next_prompt after inbound answer")
        # Return an error message but keep flow state advanced (as data was saved successfully)
        return (
            "Something went wrong while sending the next question. Please try again.",
            False,
        )

    # Refresh to know if we're done (send_next_prompt updates step/is_complete)
    sess.refresh_from_db()
    done = bool(sess.is_complete)

    # We already sent the next prompt (or DONE) inside send_next_prompt,
    # so we return an empty reply_text for the inbound message handler.
    return ("", done)


# ---------- fallback messages ----------


def get_fallback_message(scenario: str, reg=None) -> str:
    """
    Returns appropriate fallback message for users messaging outside of active flows.
    
    Args:
        scenario: One of 'no_registration', 'completed', 'unknown'
        reg: Optional EventRegistration for context
    
    Returns:
        str: User-friendly message to send via WhatsApp
    """
    if scenario == "no_registration":
        return (
            "👋 Hello! I don't have an active travel registration for you.\n\n"
            "If you're a guest for an upcoming event, you should have received "
            "an invitation to share your travel details.\n\n"
            "If you need assistance, please contact our support team. 📞"
        )
    
    elif scenario == "completed":
        event_name = ""
        if reg and hasattr(reg, 'event') and reg.event:
            event_name = f" for {reg.event.name}"
        
        return (
            f"✅ Thank you! We've already received your travel details{event_name}.\n\n"
            "If you need to change anything, simply reply with *update* to see your options.\n\n"
            "Or contact our support team for assistance. 📞"
        )
    
    else:
        # Generic unknown scenario
        return (
            "Hi! I'm here to help with travel arrangements for your event.\n\n"
            "If you have questions or need assistance, please contact our support team. 📞"
        )
