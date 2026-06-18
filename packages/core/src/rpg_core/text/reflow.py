"""Reflow PDF line breaks and hyphenation for readable chunk text."""

from __future__ import annotations

import re

_SPECIAL_SPACE = re.compile(r"[\u00a0\u202f]")
_TRAILING_HYPHEN = re.compile(
    r"[-\u00ad\u2010\u2011\u2012\u2013\u2014\u2015\u2212]+$"
)
_MULTI_SPACE = re.compile(r" {2,}")


def reflow_chunk_text(text: str) -> str:
    """Normalize special spaces, join wrapped lines, handle end-of-line hyphenation."""
    normalized = _SPECIAL_SPACE.sub(" ", text)
    paragraphs = re.split(r"\n\s*\n", normalized)
    return "\n\n".join(
        reflowed
        for reflowed in (_reflow_paragraph(paragraph) for paragraph in paragraphs)
        if reflowed
    )


def _reflow_paragraph(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
    if not lines:
        return ""

    result = lines[0]
    for line in lines[1:]:
        if _TRAILING_HYPHEN.search(result):
            result = _TRAILING_HYPHEN.sub("", result) + line
        else:
            result += f" {line}"
    return _MULTI_SPACE.sub(" ", result).strip()
