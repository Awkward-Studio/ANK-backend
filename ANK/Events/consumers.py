import logging
import uuid
import datetime
import decimal
from typing import Any, Dict

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


def _json_safe(obj: Any) -> Any:
    """
    Recursively convert common non-JSON-serializable types to JSON-safe values.
    - UUID -> str
    - datetime/date -> ISO string
    - Decimal -> float
    - dict/list/tuple/set -> converted containers
    All other unknown objects -> str(obj)
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        # Keep tz info if present
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    # Fallback: stringify unknowns
    return str(obj)


class EventRegistrationConsumer(AsyncJsonWebsocketConsumer):
    """
    Each client connects to:  ws://<host>/ws/events/<event_id>/
    Joins group:               event_<event_id>
    Server (signals.py) should broadcast with:
        channel_layer.group_send(
            f"event_{event_id}",
            {
                "type": "rsvp_update",  # <- MUST match handler name below
                "data": { ... JSON-safe payload ... }
            }
        )
    """

    group_name: str = ""
    event_id: str = ""

    async def connect(self):
        try:
            # 1) Extract event_id from URL params
            event_id = self.scope.get("url_route", {}).get("kwargs", {}).get("event_id")
            if not event_id:
                logger.warning("WS connect missing event_id")
                await self.close(code=4400)  # 4400 Bad Request (custom)
                return

            # 2) Validate UUID format early (prevents group pollution)
            try:
                uuid.UUID(event_id)
            except Exception:
                logger.warning("WS connect invalid event_id format: %r", event_id)
                await self.close(code=4400)
                return

            self.event_id = event_id
            self.group_name = f"event_{self.event_id}"

            # TODO: Optional auth here (cookies/JWT), reject if unauthorized

            # 3) Join group & accept
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                "WS CONNECT ok: event=%s chan=%s", self.event_id, self.channel_name
            )

        except Exception as e:
            logger.exception("WebSocket connect failed: %s", e)
            # Don’t raise; close cleanly
            try:
                await self.close(code=4000)
            except Exception:
                pass

    async def disconnect(self, code):
        try:
            if self.group_name:
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
            logger.info("WS DISCONNECT: event=%s code=%s", self.event_id, code)
        except Exception:
            logger.exception("WebSocket disconnect cleanup failed")

    async def receive(self, text_data=None, bytes_data=None):
        """
        No client → server messages expected.
        You can add ping/pong or simple echo handling here if needed.
        """
        try:
            # ignore any client input to prevent abuse
            return
        except Exception:
            logger.exception("Error handling client message")

    # ---------------------------
    # Group message handlers
    # ---------------------------

    async def rsvp_update(self, event: Dict[str, Any]):
        """
        Handler name MUST match the 'type' key in group_send payload.
        Sends JSON-SAFE data to client.
        Expected shape:
            event = {
              "type": "rsvp_update",
              "data": {...}  # may contain UUID/datetime etc.
            }
        """
        try:
            raw = event.get("data", {})
            safe = _json_safe(raw)
            await self.send_json(safe)
        except Exception:
            logger.exception("Failed to send rsvp_update to client")
            # Close this socket to avoid noisy error loops; client can reconnect
            try:
                await self.close(code=4001)
            except Exception:
                pass
