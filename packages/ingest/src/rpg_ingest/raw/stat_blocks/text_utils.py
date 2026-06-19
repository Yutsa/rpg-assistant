from __future__ import annotations

import re

PUA_RE = re.compile(r"[\uE000-\uF8FF]")
ICON_LINE_RE = re.compile(r"^W\s*$")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
DRM_NAME_LINE_RE = re.compile(r"^W\s+(.+)$")


def normalize_spaces(text: str) -> str:
    return text.replace("\u202f", " ").replace("\xa0", " ")


def _clean_line(line: str) -> str:
    stripped = CONTROL_CHAR_RE.sub("", PUA_RE.sub("", line)).strip()
    if not stripped:
        return ""
    drm_match = DRM_NAME_LINE_RE.match(stripped)
    if drm_match:
        stripped = drm_match.group(1).strip()
    return stripped


def strip_layout_glyphs(text: str) -> str:
    """Remove CoF layout icon glyphs (PUA chars and lone W lines)."""
    lines = []
    for line in normalize_spaces(text).splitlines():
        stripped = _clean_line(line)
        if not stripped or ICON_LINE_RE.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def has_icon_glyphs(text: str) -> bool:
    if PUA_RE.search(text):
        return True
    return any(ICON_LINE_RE.match(line.strip()) for line in text.splitlines() if line.strip())
