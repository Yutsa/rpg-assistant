from __future__ import annotations

import re

PUA_RE = re.compile(r"[\uE000-\uF8FF]")
ICON_LINE_RE = re.compile(r"^W\s*$")


def normalize_spaces(text: str) -> str:
    return text.replace("\u202f", " ").replace("\xa0", " ")


def strip_layout_glyphs(text: str) -> str:
    """Remove CoF layout icon glyphs (PUA chars and lone W lines)."""
    lines = []
    for line in normalize_spaces(text).splitlines():
        stripped = PUA_RE.sub("", line).strip()
        if not stripped or ICON_LINE_RE.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def has_icon_glyphs(text: str) -> bool:
    if PUA_RE.search(text):
        return True
    return any(ICON_LINE_RE.match(line.strip()) for line in text.splitlines() if line.strip())
