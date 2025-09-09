import re
from typing import Any, Dict
from MessageTemplates.models import MessageTemplate

# Matches {{1}}, {{2}}, etc.
_PLACEHOLDER = re.compile(r"\{\{\s*(\d+)\s*\}\}")


def _resolve_path(obj: Any, path: str) -> Any:
    """
    Resolve dotted path (case-insensitive). Supports list indexes.
    e.g. Guest.name, Event.start_date, Travel.0.arrival_date
    """
    cur = obj
    for seg in path.split("."):
        key = seg.lower()
        if isinstance(cur, dict):
            lower_map = {str(k).lower(): v for k, v in cur.items()}
            cur = lower_map.get(key, "")
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if 0 <= idx < len(cur) else ""
        else:
            return ""
    return "" if cur is None else cur


def render_template_with_vars(tmpl: MessageTemplate, context: Dict[str, Any]) -> str:
    """
    Replace {{1}}, {{2}}, etc. with resolved values from tmpl.variables.
    """
    mapping = {v.variable_name: v.variable_value for v in tmpl.variables.all()}

    def repl(m: re.Match) -> str:
        num = m.group(1)
        field_path = mapping.get(num, "")
        if not field_path:
            return ""  # missing mapping → empty
        return str(_resolve_path(context, field_path))

    return _PLACEHOLDER.sub(repl, tmpl.message or "")
