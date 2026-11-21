import re
from html import escape

from urllib.parse import urlsplit


def render_content(content, link_url, lists):
    """Render Docs structural elements using escaped text and fixed HTML elements."""
    parts = []
    open_lists = []

    def close_lists(depth):
        while len(open_lists) > depth:
            parts.append(f"</li></{open_lists.pop()}>")

    for element in content:
        if "paragraph" in element:
            paragraph = element["paragraph"]
            style = paragraph.get("paragraphStyle", {})
            heading = re.fullmatch(r"HEADING_([1-6])", style.get("namedStyleType", ""))
            tag = f"h{heading[1]}" if heading else "p"
            if style.get("namedStyleType") in {"TITLE", "SUBTITLE"}:
                tag = "h2" if style["namedStyleType"] == "TITLE" else "h3"
            body = "".join(render_run(run, link_url) for run in paragraph.get("elements", []))
            bullet = style.get("bullet")
            if bullet:
                levels = lists.get(bullet.get("listId"), {}).get("listProperties", {}).get("nestingLevels", [])
                index = min(bullet.get("nestingLevel", 0), len(open_lists))
                level = levels[index] if index < len(levels) else {}
                kind = "ol" if level.get("glyphType") not in (None, "NONE", "GLYPH_TYPE_UNSPECIFIED") else "ul"
                close_lists(index + 1)
                if len(open_lists) > index and open_lists[-1] != kind:
                    close_lists(index)
                if len(open_lists) == index:
                    start = level.get("startNumber", 1)
                    attribute = f' start="{start}"' if kind == "ol" and isinstance(start, int) else ""
                    parts.append(f"<{kind}{attribute}><li>")
                    open_lists.append(kind)
                else:
                    parts.append("</li><li>")
                parts.append(body)
            else:
                close_lists(0)
                alignment = {"CENTER": "center", "END": "end", "JUSTIFIED": "justify"}.get(style.get("alignment"))
                attribute = f' style="text-align:{alignment}"' if alignment else ""
                parts.append(f"<{tag}{attribute}>{body or '<br>'}</{tag}>")
        elif "table" in element:
            close_lists(0)
            parts.append("<table><tbody>")
            for row in element["table"].get("tableRows", []):
                parts.append("<tr>")
                for cell in row.get("tableCells", []):
                    style = cell.get("tableCellStyle", {})
                    spans = "".join(
                        f' {attr}="{value}"'
                        for attr, field in (("colspan", "columnSpan"), ("rowspan", "rowSpan"))
                        if isinstance(value := style.get(field), int) and value > 1
                    )
                    parts.append(f"<td{spans}>")
                    parts.append(render_content(cell.get("content", []), link_url, lists))
                    parts.append("</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
        elif "sectionBreak" in element:
            close_lists(0)
    close_lists(0)
    return "".join(parts)


def render_run(element, link_url):
    run = element.get("textRun", {})
    style = run.get("textStyle", {})
    content = escape(run.get("content", "").removesuffix("\n")).replace("\n", "<br>")
    link = style.get("link", {})
    if "richLink" in element:
        rich = element["richLink"].get("richLinkProperties", {})
        content = escape(rich.get("title") or rich.get("uri") or "")
        link = {"url": rich.get("uri")}
    elif "person" in element:
        person = element["person"].get("personProperties", {})
        content = escape(person.get("name") or person.get("email") or "")
    elif "inlineObjectElement" in element:
        content = "<em>[Embedded content]</em>"
    for key, tag in (("bold", "strong"), ("italic", "em"), ("underline", "u"), ("strikethrough", "s")):
        if style.get(key):
            content = f"<{tag}>{content}</{tag}>"
    baseline = {"SUBSCRIPT": "sub", "SUPERSCRIPT": "sup"}.get(style.get("baselineOffset"))
    if baseline:
        content = f"<{baseline}>{content}</{baseline}>"
    colors = []
    for key, css in (("foregroundColor", "color"), ("backgroundColor", "background-color")):
        rgb = style.get(key, {}).get("color", {}).get("rgbColor")
        if rgb is not None:
            color = ",".join(str(round(min(1, max(0, rgb.get(channel, 0))) * 255)) for channel in ("red", "green", "blue"))
            colors.append(f"{css}:rgb({color})")
    if colors:
        content = f'<span style="{";".join(colors)}">{content}</span>'
    url = link_url(link)
    try:
        safe_link = urlsplit(url)
        if safe_link.scheme in {"https", "http"} and safe_link.hostname and not safe_link.username:
            return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{content}</a>'
    except ValueError:
        pass
    return content


STEP_HEADING = re.compile(r"(?:suggested\s+)?(?:next\s+steps|action\s+items)\s*:?", re.IGNORECASE)
SECTION_HEADING = re.compile(r"(?:details|decisions|summary|meeting records|transcript)\s*:?", re.IGNORECASE)
STEP = re.compile(r"^(?:\[([^\]]+)\]\s*)?([^:]+):\s*(.*)$")


def suggested_steps(text):
    steps = []
    active = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if STEP_HEADING.fullmatch(line):
            active = True
            continue
        if not active:
            continue
        if SECTION_HEADING.fullmatch(line) or DECISION_GROUP.fullmatch(line):
            break
        match = STEP.match(line)
        if match:
            owner, title, description = match.groups()
            steps.append({"owner": (owner or "").strip(), "title": title.strip(), "description": description})
        elif steps:
            steps[-1]["description"] += f"\n{line}"
        else:
            steps.append({"owner": "", "title": line, "description": ""})
    return steps


DECISIONS_HEADING = re.compile(r"(?:key\s+)?decisions(?:\s+(?:made|taken))?\s*:?", re.IGNORECASE)
DECISION_GROUP = re.compile(
    r"(?:confirmed|aligned|agreed|decided|finalized|decisions made|needs further discussions?|disagreed|shelved|pending|deferred|open questions|discussion points|items for discussion|unresolved(?: items)?)\s*:?",
    re.IGNORECASE,
)


DISCUSSION_LABEL = re.compile(r"discussion|disagreed|shelved|pending|deferred|open questions|unresolved", re.IGNORECASE)


def is_discussion_group(label):
    return bool(DISCUSSION_LABEL.search(label))


SUMMARY_HEADING = re.compile(
    r"(?:meeting summary|summary|overview|quick notes|(?:key |main )?takeaways|(?:meeting )?highlights)\s*:?",
    re.IGNORECASE,
)
DETAILS_HEADING = re.compile(r"(?:details|discussion topics|discussion details)\s*:?", re.IGNORECASE)
NOTES_FOOTER = re.compile(r"^(?:you should review gemini|how is the quality|want to see more)", re.IGNORECASE)


def meeting_summary(text, *, quick=False):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    has_heading = any(SUMMARY_HEADING.fullmatch(line) for line in lines)
    paragraphs = []
    active = quick and not has_heading
    for line in lines:
        if SUMMARY_HEADING.fullmatch(line):
            active = True
            continue
        if not active:
            continue
        if (SECTION_HEADING.fullmatch(line) or DECISIONS_HEADING.fullmatch(line)
                or STEP_HEADING.fullmatch(line) or DECISION_GROUP.fullmatch(line)
                or DETAILS_HEADING.fullmatch(line) or NOTES_FOOTER.match(line)):
            break
        if quick and re.match(r"^(?:invited|attachments|meeting records)\b", line, re.IGNORECASE):
            continue
        paragraphs.append(line)
    return "\n".join(paragraphs)


def discussion_topics(text):
    active = False
    titles = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if DETAILS_HEADING.fullmatch(line):
            active = True
            continue
        if not active or not line:
            continue
        if (NOTES_FOOTER.match(line) or SUMMARY_HEADING.fullmatch(line)
                or DECISIONS_HEADING.fullmatch(line) or STEP_HEADING.fullmatch(line)):
            break
        title, colon, _ = line.partition(":")
        if colon and 5 <= len(title) <= 140 and not re.search(r"[.!?]\s", title):
            titles.append(title.strip())
    return list(dict.fromkeys(titles))


def decision_groups(text):
    groups = []
    active = False
    group = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if DECISIONS_HEADING.fullmatch(line):
            active = True
            group = None
            continue
        if SECTION_HEADING.fullmatch(line) or STEP_HEADING.fullmatch(line):
            active = False
            group = None
            continue
        is_group = bool(DECISION_GROUP.fullmatch(line))
        if not active and not (is_group and is_discussion_group(line)):
            continue
        if is_group:
            active = True
            group = {"label": line.rstrip(":"), "items": []}
            groups.append(group)
            continue
        if group is None:
            group = {"label": "", "items": []}
            groups.append(group)
        group["items"].append(line)
    return [group for group in groups if group["items"]]
