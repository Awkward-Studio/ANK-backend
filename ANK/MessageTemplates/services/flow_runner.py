import logging
import re
from datetime import datetime, date
from typing import Tuple, Optional, Any
from django.db import transaction

from MessageTemplates.models import FlowSession
from Events.services.message_logger import MessageLogger

logger = logging.getLogger("whatsapp_flows")


class FlowRunner:
    """
    Executes a visual conversation flow (Directed Acyclic Graph) for a WhatsApp session.
    """

    def __init__(self, session: FlowSession, sender_phone_number_id: str = None):
        self.session = session
        self.flow = session.flow
        self.sender_phone_number_id = sender_phone_number_id
        
        graph = self.flow.graph_json or {}
        self.nodes = {str(n["id"]): n for n in graph.get("nodes", [])}
        self.edges = graph.get("edges", [])

    def _set_status(self, status: str):
        self.session.status = status
        self.session.save(update_fields=["status", "last_interaction"])

    def _set_error(self, reason: str):
        logger.error("[FLOW] %s | session=%s flow=%s", reason, self.session.id, self.flow.id)
        self.session.status = "ERROR"
        context = dict(self.session.context_data or {})
        context["_last_error"] = reason
        self.session.context_data = context
        self.session.save(update_fields=["status", "context_data", "last_interaction"])

    def start(self):
        """Starts the flow by triggering the first node."""
        if self.session.status != "RUNNING":
            return
            
        start_nodes = [n for n in self.nodes.values() if n.get("type") == "trigger"]
        if not start_nodes:
            incoming_edges = {e.get("target") for e in self.edges}
            start_nodes = [n for n in self.nodes.values() if n["id"] not in incoming_edges]
            
        if not start_nodes:
            self._set_error("No trigger node found")
            return
            
        first_node = start_nodes[0]
        self._execute_node(first_node["id"])

    @transaction.atomic
    def process_input(self, text: str, payload_type: str = "text") -> Tuple[str, bool]:
        if self.session.status != "WAITING_FOR_INPUT":
            return "", self.session.status == "COMPLETED"

        current_node_id = self.session.current_node_id
        if not current_node_id or current_node_id not in self.nodes:
            self._set_error("Current node missing during input processing")
            return "An error occurred with this flow.", False

        node = self.nodes[current_node_id]
        is_valid, parsed_value, error_msg = self._validate_input(node, text, payload_type)
        
        if not is_valid:
            return error_msg or "Invalid input. Please try again.", False
            
        self.session.context_data[current_node_id] = parsed_value
        self.session.save(update_fields=["context_data", "last_interaction"])
        
        next_node_id = self._get_next_node_id(current_node_id, parsed_value)
        
        if not next_node_id:
            self._complete_session()
            return "", True
            
        self.session.status = "RUNNING"
        self._execute_node(next_node_id)
        
        return "", self.session.status == "COMPLETED"

    def _execute_node(self, node_id: str):
        if node_id not in self.nodes:
            self._set_error(f"Missing node '{node_id}'")
            return
            
        node = self.nodes[node_id]
        node_type = node.get("type")
        node_data = node.get("data", {})
        
        self.session.current_node_id = node_id
        self.session.save(update_fields=["current_node_id", "last_interaction"])

        if node_type == "trigger":
            if node_data.get("startWithTemplate") and node_data.get("initialTemplateName"):
                MessageLogger.send_template(
                    self.session.registration,
                    node_data.get("initialTemplateName"),
                    "flow",
                    phone_number_id=self.sender_phone_number_id
                )
            
            next_id = self._get_next_node_id(node_id)
            if next_id: self._execute_node(next_id)
            else: self._complete_session()

        elif node_type == "message":
            text = self._interpolate_string(node_data.get("text", ""))
            buttons = node_data.get("buttons", [])
            
            if buttons:
                button_list = [{"id": f"flow|{node_id}|{b['value']}", "title": b["label"]} for b in buttons]
                MessageLogger.send_buttons(self.session.registration, text, button_list, "flow", phone_number_id=self.sender_phone_number_id)
                self._set_status("WAITING_FOR_INPUT")
            else:
                MessageLogger.send_text(self.session.registration, text, "flow", phone_number_id=self.sender_phone_number_id)
                next_id = self._get_next_node_id(node_id)
                if next_id: self._execute_node(next_id)
                else: self._complete_session()
                
        elif node_type == "input":
            prompt = self._interpolate_string(node_data.get("prompt", ""))
            buttons = node_data.get("buttons", [])
            
            if buttons:
                button_list = [{"id": f"flow|{node_id}|{b['value']}", "title": b["label"]} for b in buttons]
                MessageLogger.send_buttons(self.session.registration, prompt, button_list, "flow", phone_number_id=self.sender_phone_number_id)
            else:
                MessageLogger.send_text(self.session.registration, prompt, "flow", phone_number_id=self.sender_phone_number_id)
                
            self._set_status("WAITING_FOR_INPUT")

        elif node_type == "template":
            template_name = node_data.get("templateName")
            if template_name:
                MessageLogger.send_template(self.session.registration, template_name, "flow", phone_number_id=self.sender_phone_number_id)
            
            has_button_edges = any(e.get("source") == node_id and e.get("sourceHandle") for e in self.edges)
            if has_button_edges:
                self._set_status("WAITING_FOR_INPUT")
            else:
                next_id = self._get_next_node_id(node_id)
                if next_id: self._execute_node(next_id)
                else: self._complete_session()

        elif node_type == "logic":
            val = self._resolve_variable(node_data.get("field", ""))
            op = node_data.get("operator", "==")
            target = node_data.get("value", "")
            
            result = False
            if op == "==": result = str(val).lower() == str(target).lower()
            elif op == "!=": result = str(val).lower() != str(target).lower()
            elif op == ">":
                try:
                    result = float(val) > float(target)
                except (TypeError, ValueError):
                    result = False
            elif op == "<":
                try:
                    result = float(val) < float(target)
                except (TypeError, ValueError):
                    result = False
            elif op == "contains": result = str(target).lower() in str(val).lower()
            
            next_id = self._get_next_node_id(node_id, "true" if result else "false")
            if next_id: self._execute_node(next_id)
            else: self._complete_session()
                
        elif node_type == "orm_update":
            self._execute_orm_update(node_data)
            if self.session.status == "ERROR":
                return
            next_id = self._get_next_node_id(node_id)
            if next_id: self._execute_node(next_id)
            else: self._complete_session()
        else:
            self._set_error(f"Unsupported node type '{node_type}'")

    def _complete_session(self):
        self._set_status("COMPLETED")

    def _get_next_node_id(self, current_node_id: str, last_value: Any = None) -> Optional[str]:
        val_str = str(last_value).lower().strip() if last_value else None
        if val_str:
            for edge in self.edges:
                if edge.get("source") == current_node_id and edge.get("sourceHandle"):
                    if str(edge.get("sourceHandle")).lower().strip() == val_str:
                        return edge.get("target")
        for edge in self.edges:
            if edge.get("source") == current_node_id and not edge.get("sourceHandle"):
                return edge.get("target")
        return None

    def _validate_input(self, node: dict, text: str, payload_type: str) -> Tuple[bool, Any, Optional[str]]:
        data = node.get("data", {})
        val_type = data.get("validation", "text")
        text = text.strip() if text else ""
        
        if node.get("type") == "template" or val_type == "choice":
            return True, text, None
            
        if val_type == "date":
            parsed = self._parse_date(text)
            if parsed: return True, parsed.isoformat(), None
            return False, None, "📅 Please provide a valid date (e.g., 15-03-2026 or 15th March)."

        if val_type == "time":
            parsed = self._parse_time(text)
            if parsed: return True, parsed, None
            return False, None, "⏰ Please provide a valid time (e.g., 14:30 or 2:30 PM)."

        if val_type == "pnr":
            if len(text) >= 5 and len(text) <= 10: return True, text.upper(), None
            return False, None, "🎫 Please provide a valid PNR/Booking code (5-10 characters)."

        if val_type == "number":
            try: return True, int(text), None
            except: return False, None, "🔢 Please enter a numeric value."
                
        return True, text, None

    def _parse_date(self, text: str) -> Optional[date]:
        """Sophisticated date parser from travel_info_capture."""
        clean = re.sub(r'(st|nd|rd|th)', '', text, flags=re.IGNORECASE)
        formats = ["%d-%m-%Y", "%d/%m/%Y", "%d %m %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(clean, fmt).date()
                if dt.year < 2000: dt = dt.replace(year=dt.year + 2000)
                return dt
            except: continue
        return None

    def _parse_time(self, text: str) -> Optional[str]:
        """Sophisticated time parser from travel_info_capture."""
        t = text.lower().replace(".", "").replace(" ", "")
        m = re.search(r'(\d{1,2})[:h]?(\d{2})?\s*(am|pm)?', t)
        if not m: return None
        hh, mm, ampm = m.groups()
        hh = int(hh)
        mm = int(mm) if mm else 0
        if ampm == "pm" and hh < 12: hh += 12
        elif ampm == "am" and hh == 12: hh = 0
        if 0 <= hh < 24 and 0 <= mm < 60: return f"{hh:02d}:{mm:02d}"
        return None

    def _resolve_variable(self, path: str) -> Any:
        if not path: return ""
        if path.startswith("guest."):
            field = path.split(".")[1]
            return getattr(self.session.registration.guest, field, "")
        if path in self.session.context_data:
            return self.session.context_data[path]
        return ""

    def _interpolate_string(self, text: str) -> str:
        reg = self.session.registration
        if reg and reg.guest:
            text = text.replace("{{guest.name}}", str(reg.guest.name or "Guest"))
        for node_id, value in self.session.context_data.items():
            text = text.replace(f"{{{{{node_id}}}}}", str(value))
        return text

    def _execute_orm_update(self, node_data: dict):
        model_name = node_data.get("model")
        mappings = node_data.get("mappings", [])
        if not model_name or not mappings:
            return
            
        if model_name == "TravelDetail":
            from Logistics.models.travel_details_models import TravelDetail
            reg = self.session.registration
            td = TravelDetail.objects.filter(event=reg.event, event_registrations=reg).first()
            if not td:
                td = TravelDetail.objects.create(event=reg.event, arrival="commercial", departure="commercial")
                td.event_registrations.add(reg)
            
            for m in mappings:
                val = self.session.context_data.get(m.get("source_node"))
                if val: setattr(td, m.get("field"), val)
            td.save()
            return

        self._set_error(f"Unsupported ORM target '{model_name}'")
