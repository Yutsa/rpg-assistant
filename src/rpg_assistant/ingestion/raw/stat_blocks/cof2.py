from __future__ import annotations

import re

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.stat_blocks.text_utils import has_icon_glyphs, strip_layout_glyphs
from rpg_assistant.ingestion.raw.stat_blocks.types import (
    BlockRef,
    ParsedStatBlock,
    StatAbility,
    StatBlockSpan,
)
from rpg_assistant.storage.ids import new_id

NC_RE = re.compile(r"\|\s*NC\s*(\d+)", re.IGNORECASE)
NAME_NC_RE = re.compile(
    r"^(.+?)\s*\|\s*NC\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE
)
STATS_LINE_RE = re.compile(
    r"\b(AGI|FOR|CON|INT|PER|CHA|VOL)\s*([+-])\s*(\d+)", re.IGNORECASE
)
STATS_LINE_START_RE = re.compile(
    r"^(AGI|FOR|CON|INT|PER|CHA|VOL)\s*[+-]?\s*\d", re.IGNORECASE
)
STAT_BLOCK_BODY_RE = re.compile(
    r"\b(DEF|PV|Init|PM)\b|Voie de|Voir le profil",
    re.IGNORECASE,
)
ABILITY_TITLE_RE = re.compile(r"^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-']+)\s*:\s*(.*)$", re.DOTALL)
ALL_CAPS_NAME_RE = re.compile(r"^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-,'\.]{1,58}$")

COF_ATTRIBUTES = frozenset({"AGI", "FOR", "CON", "INT", "PER", "CHA", "VOL"})
TYPE_LABEL_WORDS = frozenset(
    {
        "HUMAINE",
        "HUMAIN",
        "MORT-VIVANT",
        "MORT-VIVANTS",
        "MORT VIVANT",
        "ANIMAUX",
        "ANIMAL",
        "CONSTRUCT",
        "ESPRIT",
    }
)

CHAPTER_RE = re.compile(
    r"^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b",
    re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
RUNNING_PAGE_HEADER_RE = re.compile(r"^PAGE\s+\d+\s*$", re.IGNORECASE)


def _normalized(block: LayoutBlock) -> str:
    return strip_layout_glyphs(block.text)


def _is_stats_line(text: str) -> bool:
    normalized = strip_layout_glyphs(text)
    if not normalized:
        return False
    matches = STATS_LINE_RE.findall(normalized)
    return len(matches) >= 2


def _has_nc(text: str) -> bool:
    return bool(NC_RE.search(strip_layout_glyphs(text)))


def _is_icon_block(block: LayoutBlock) -> bool:
    if block.metadata.get("stat_block_role") == "icon":
        return True
    return has_icon_glyphs(block.text) and not strip_layout_glyphs(block.text)


def _is_type_label(text: str) -> bool:
    normalized = text.strip().upper()
    return normalized in TYPE_LABEL_WORDS


def _is_running_page_header(text: str) -> bool:
    return bool(RUNNING_PAGE_HEADER_RE.match(text.strip()))


def _is_icon_prefixed_name(block: LayoutBlock) -> bool:
    if not has_icon_glyphs(block.text):
        return False
    text = _normalized(block)
    if not text or _is_running_page_header(text):
        return False
    return ALL_CAPS_NAME_RE.match(text) or _has_nc(text)


def _is_stat_header_block(block: LayoutBlock, page_blocks: list[LayoutBlock], idx: int) -> bool:
    if _is_icon_prefixed_name(block):
        return True
    text = _normalized(block)
    if not text or _is_running_page_header(text):
        return False
    if _has_nc(text):
        return True
    if _is_stats_line(text):
        return False
    if STATS_LINE_START_RE.match(text) and _is_stats_line(text):
        return False
    if _is_type_label(text):
        return False

    next_block = page_blocks[idx + 1] if idx + 1 < len(page_blocks) else None
    if next_block and _is_stats_line(_normalized(next_block)):
        candidate = text
        if _is_type_label(candidate):
            return False
        if ALL_CAPS_NAME_RE.match(candidate) or "," in candidate:
            return True
        if block.metadata.get("is_bold") and candidate.isupper():
            return True

    return False


def _is_ability_block(block: LayoutBlock) -> bool:
    text = _normalized(block)
    if not text:
        return False
    if _is_stats_line(text) or _has_nc(text):
        return False
    if ":" in text:
        first_line = text.split("\n", 1)[0]
        if ABILITY_TITLE_RE.match(first_line) or (
            block.metadata.get("is_bold") and first_line.rstrip().endswith(":")
        ):
            return True
    return False


def _parse_ability_block(text: str) -> StatAbility | None:
    lines = [line.strip() for line in strip_layout_glyphs(text).splitlines() if line.strip()]
    if not lines:
        return None
    first_match = ABILITY_TITLE_RE.match(lines[0])
    if not first_match:
        return None
    title = first_match.group(1).strip()
    if not title:
        return None
    body_parts: list[str] = []
    inline_body = first_match.group(2).strip()
    if inline_body:
        body_parts.append(inline_body)
    body_parts.extend(lines[1:])
    body = "\n".join(body_parts).strip()
    return StatAbility(title=title, text=body)


def _is_stat_continuation(block: LayoutBlock) -> bool:
    text = _normalized(block)
    if not text:
        return False
    if _is_type_label(text):
        return True
    if _is_stats_line(text):
        return True
    if _is_ability_block(block):
        return True
    if STAT_BLOCK_BODY_RE.search(text):
        return True
    if _has_nc(text):
        return False
    role = block.metadata.get("stat_block_role")
    if role in {"stats", "ability", "body"}:
        return True
    if len(text) <= 200 and block.metadata.get("is_bold"):
        return ":" in text
    return len(text) <= 120 and not CHAPTER_RE.match(text) and not NUMBERED_HEADING_RE.match(text)


def _is_real_section_heading(block: LayoutBlock) -> bool:
    text = strip_layout_glyphs(block.text)
    if CHAPTER_RE.match(text):
        return True
    if NUMBERED_HEADING_RE.match(text) and block.metadata.get("is_bold"):
        return True
    return False


def _ends_stat_block(
    block: LayoutBlock, page_blocks: list[LayoutBlock], idx: int
) -> bool:
    if _is_real_section_heading(block):
        return True
    if _is_icon_prefixed_name(block):
        return True
    if _is_stat_header_block(block, page_blocks, idx):
        return True
    text = _normalized(block)
    if not text or _is_ability_block(block) or _is_stats_line(text):
        return False
    if block.metadata.get("is_bold"):
        font = block.metadata.get("max_font_size") or 0
        if font >= 12 and not text.isupper():
            return not STAT_BLOCK_BODY_RE.search(text)
    return False


class Cof2StatBlockProfile:
    profile_id = "cof2"
    aliases = [
        "cof2",
        "cof 2",
        "chroniques oubliées fantasy 2",
        "chroniques oubliees fantasy 2",
        "chroniques oubliées",
        "chroniques oubliees",
    ]

    def matches_document(self, pages: list[LayoutPage]) -> bool:
        nc_count = 0
        stats_count = 0
        for page in pages:
            for block in page.blocks:
                text = _normalized(block)
                if _has_nc(text):
                    nc_count += 1
                if _is_stats_line(text):
                    stats_count += 1
        return nc_count >= 1 and stats_count >= 1

    def is_false_heading(
        self,
        block: LayoutBlock,
        page_blocks: list[LayoutBlock],
        block_idx: int,
    ) -> bool:
        role = block.metadata.get("stat_block_role")
        if role in {"header", "stats", "icon"}:
            return True
        text = _normalized(block)
        if not text or _is_running_page_header(text):
            return False
        if _has_nc(text):
            return True
        if _is_stats_line(text):
            return True
        if _is_icon_block(block):
            return True
        if _is_icon_prefixed_name(block):
            return True
        if _is_type_label(text):
            return True
        return _is_stat_header_block(block, page_blocks, block_idx)

    def detect_spans(self, pages: list[LayoutPage]) -> list[StatBlockSpan]:
        spans: list[StatBlockSpan] = []
        pending_icons: list[LayoutBlock] = []

        def attach_icons(span_id: str, target: list[LayoutBlock]) -> None:
            for icon in pending_icons:
                icon.metadata["stat_block_id"] = span_id
                icon.metadata["stat_block_role"] = "icon"
                target.append(icon)
            pending_icons.clear()

        def flush_span(span_id: str, span_blocks: list[LayoutBlock]) -> None:
            if not span_blocks:
                return
            page_numbers = [b.page_number for b in span_blocks]
            spans.append(
                StatBlockSpan(
                    id=span_id,
                    blocks=list(span_blocks),
                    page_start=min(page_numbers),
                    page_end=max(page_numbers),
                )
            )

        for page in pages:
            blocks = page.blocks
            idx = 0
            while idx < len(blocks):
                block = blocks[idx]

                if _is_icon_block(block):
                    pending_icons.append(block)
                    idx += 1
                    continue

                if _is_stat_header_block(block, blocks, idx):
                    span_id = new_id("sb")
                    span_blocks: list[LayoutBlock] = []
                    attach_icons(span_id, span_blocks)
                    block.metadata["stat_block_id"] = span_id
                    block.metadata["stat_block_role"] = "header"
                    span_blocks.append(block)
                    idx += 1
                    while idx < len(blocks):
                        nxt = blocks[idx]
                        if _is_icon_block(nxt):
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "icon"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        if _ends_stat_block(nxt, blocks, idx):
                            break
                        nxt_text = _normalized(nxt)
                        if _is_stats_line(nxt_text):
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "stats"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        if _is_ability_block(nxt):
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "ability"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        if _is_stat_continuation(nxt) and span_blocks:
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "body"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        break
                    flush_span(span_id, span_blocks)
                    continue

                idx += 1

        pending_icons.clear()
        return spans

    def parse_span(self, span: StatBlockSpan) -> ParsedStatBlock:
        texts = [self.normalize_block_text(block.text) for block in span.blocks]
        combined = "\n\n".join(t for t in texts if t)
        name = ""
        subtitle: str | None = None
        nc: int | None = None
        attributes: dict[str, int] = {}
        abilities: list[StatAbility] = []

        for text in texts:
            if not text:
                continue
            header_match = NAME_NC_RE.search(text)
            if header_match:
                header_part = header_match.group(1).strip()
                nc = int(header_match.group(2))
                if "," in header_part:
                    name_part, sub_part = header_part.split(",", 1)
                    name = name_part.strip()
                    subtitle = sub_part.strip()
                else:
                    name = header_part
            elif _has_nc(text):
                nc_match = NC_RE.search(text)
                if nc_match:
                    nc = int(nc_match.group(1))
                header_part = NC_RE.split(text)[0].strip().rstrip("|").strip()
                if "," in header_part:
                    name_part, sub_part = header_part.split(",", 1)
                    if not name:
                        name = name_part.strip()
                    if not subtitle:
                        subtitle = sub_part.strip()
                elif not name and header_part:
                    name = header_part

            for attr, sign, value in STATS_LINE_RE.findall(text):
                key = attr.upper()
                if key in COF_ATTRIBUTES:
                    attributes[key] = int(value) if sign == "+" else -int(value)

        for block in span.blocks:
            if block.metadata.get("stat_block_role") != "ability":
                continue
            ability = _parse_ability_block(self.normalize_block_text(block.text))
            if ability and ability.title not in {a.title for a in abilities}:
                abilities.append(ability)

        if not name:
            for text in texts:
                candidate = text.strip()
                if candidate and ALL_CAPS_NAME_RE.match(candidate) and not _is_stats_line(candidate):
                    name = candidate.split(",")[0].strip()
                    break

        block_refs = [
            BlockRef(page_number=block.page_number, block_index=block.block_index)
            for block in span.blocks
        ]
        return ParsedStatBlock(
            name=name,
            subtitle=subtitle,
            nc=nc,
            attributes=attributes,
            abilities=abilities,
            raw_text=combined,
            block_refs=block_refs,
            game_system=self.profile_id,
        )

    def normalize_block_text(self, text: str) -> str:
        return strip_layout_glyphs(text)

    def chunk_type_hint(self, text: str, blocks: list[LayoutBlock]) -> str | None:
        if any(block.metadata.get("stat_block_id") for block in blocks):
            return "stat_block"
        normalized = self.normalize_block_text(text)
        if _has_nc(normalized) or _is_stats_line(normalized):
            return "stat_block"
        return None
