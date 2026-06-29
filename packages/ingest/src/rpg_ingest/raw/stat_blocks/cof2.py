from __future__ import annotations

import re

from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.reading_order import column_major_sort_key, column_side, is_page_number_label
from rpg_ingest.raw.stat_blocks.text_utils import (
    ATTACK_RE,
    DEFENSE_RE,
    INITIATIVE_RE,
    MANA_RE,
    VIGOR_RE,
    has_icon_glyphs,
    normalize_attack_separators,
    strip_layout_glyphs,
)
from rpg_ingest.raw.stat_blocks.types import (
    BlockRef,
    ParsedStatBlock,
    RulebookReference,
    StatAbility,
    StatAttack,
    StatBlockSpan,
)
from rpg_core.storage.ids import new_id

NC_RE = re.compile(r"(?:\|\s*)?NC\s*(\d+(?:/\d+)?)", re.IGNORECASE)
NAME_NC_RE = re.compile(
    r"^(.+?)\s*\|\s*NC\s*(\d+(?:/\d+)?)\s*$", re.IGNORECASE | re.MULTILINE
)
STATS_LINE_RE = re.compile(
    r"\b(AGI|FOR|CON|INT|PER|CHA|VOL)\s*([+-])\s*(\d+)", re.IGNORECASE
)
STATS_LINE_START_RE = re.compile(
    r"^(AGI|FOR|CON|INT|PER|CHA|VOL)\s*[+-]?\s*\d", re.IGNORECASE
)
STAT_BLOCK_BODY_RE = re.compile(
    r"\b(DEF|PV|Init|PM)\b|Voie de|Voir le profil|Utilisez le profil",
    re.IGNORECASE,
)
STAT_ATTACK_LINE_RE = re.compile(
    r"^(Morsure|Griffes|.+ \+\d+|.+ · DM)",
    re.IGNORECASE,
)
STAT_ABILITY_HINT_RE = re.compile(
    r"\b(DM\b|round de combat|premier round|surprise|d20|Lorsque la créature réussit)",
    re.IGNORECASE,
)
RULEBOOK_PROFILE_PATTERNS = (
    re.compile(
        r"Voir le profil de (.+?) \((?:Livre de règles, )?COF\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"Utilisez le profil du?\s+(.+?)\s+que vous trouverez dans le livre de règles de COF",
        re.IGNORECASE,
    ),
)
APOSTROPHE_CHARS = r"'\u2019"
ABILITY_TITLE_RE = re.compile(
    rf"^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-{APOSTROPHE_CHARS}]+?)\s*(?:\([A-Z]\))?\s*:\s*(.*)$",
    re.DOTALL,
)
INLINE_ABILITY_TITLE_RE = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?<![DdLl][{APOSTROPHE_CHARS}])([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-{APOSTROPHE_CHARS}]+?)\s*(?:\([A-Z]\))?\s*:\s*",
)
INLINE_ABILITY_SKIP_RE = re.compile(
    r"\b(AGI|FOR|CON|INT|PER|CHA)\s*[+-]"
    r"|\b(DEF|PV|NC|TAILLE|CRÉATURE|HUMAINE|HUMAIN)\b",
    re.IGNORECASE,
)
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


def _is_icon_prefixed_name(block: LayoutBlock) -> bool:
    if not has_icon_glyphs(block.text):
        return False
    text = _normalized(block)
    if not text or is_page_number_label(text):
        return False
    return ALL_CAPS_NAME_RE.match(text) or _has_nc(text)


def _is_stat_header_block(block: LayoutBlock, page_blocks: list[LayoutBlock], idx: int) -> bool:
    if _is_icon_prefixed_name(block):
        return True
    text = _normalized(block)
    if not text or is_page_number_label(text):
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
    first_line = text.split("\n", 1)[0]
    if STAT_ATTACK_LINE_RE.match(first_line):
        return True
    if STAT_ABILITY_HINT_RE.search(text) and block.metadata.get("is_bold"):
        return True
    if ":" in text:
        if ABILITY_TITLE_RE.match(first_line) or (
            block.metadata.get("is_bold") and first_line.rstrip().endswith(":")
        ):
            return True
    return False


def _extract_rulebook_reference(text: str) -> RulebookReference | None:
    normalized = re.sub(r"\s+", " ", strip_layout_glyphs(text))
    for pattern in RULEBOOK_PROFILE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return RulebookReference(profile_name=match.group(1).strip())
    return None


def _normalize_ability_title(title: str) -> str:
    return title.replace("\u2019", "'").replace("\u2018", "'").strip()


ABILITY_BODY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Au premier round de combat", re.IGNORECASE), "EMBUSCADE"),
    (re.compile(r"premier round de combat", re.IGNORECASE), "EMBUSCADE"),
    (re.compile(r"cible doit faire un test de PER difficulté 19", re.IGNORECASE), "EMBUSCADE"),
    (re.compile(r"Lorsque la créature réussit une attaque", re.IGNORECASE), "DÉVORER"),
    (re.compile(r"un résultat de 15-20 au d20", re.IGNORECASE), "DÉVORER"),
    (re.compile(r"Créatures souterraines.+dé malus", re.IGNORECASE | re.DOTALL), "SENSIBLE À LA LUMIÈRE"),
    (re.compile(r"lumière du soleil.*dé malus", re.IGNORECASE | re.DOTALL), "SENSIBLE À LA LUMIÈRE"),
    (re.compile(r"15-20 sur le d20", re.IGNORECASE | re.DOTALL), "COUP CRITIQUE"),
)


def _parse_nc_value(raw: str) -> int | str:
    value = raw.strip()
    if "/" in value:
        return value
    return int(re.search(r"\d+", value).group())


def _parse_combat_stats(text: str) -> dict[str, int]:
    normalized = normalize_attack_separators(strip_layout_glyphs(text))
    stats: dict[str, int] = {}
    if match := DEFENSE_RE.search(normalized):
        stats["defense"] = int(match.group(1))
    if match := VIGOR_RE.search(normalized):
        stats["vigor"] = int(match.group(1))
    if match := INITIATIVE_RE.search(normalized):
        stats["initiative"] = int(match.group(1))
    if match := MANA_RE.search(normalized):
        stats["mana"] = int(match.group(1))
    return stats


def _parse_attacks(text: str) -> list[StatAttack]:
    normalized = normalize_attack_separators(strip_layout_glyphs(text))
    attacks: list[StatAttack] = []
    for match in ATTACK_RE.finditer(normalized):
        name = match.group(1).strip()
        if not name:
            continue
        attacks.append(
            StatAttack(
                name=name,
                attack_bonus=int(match.group(2)),
                damage=match.group(3),
            )
        )
    return attacks


def _valid_ability_title(title: str) -> bool:
    cleaned = title.strip()
    return bool(cleaned) and len(cleaned) > 2 and cleaned != "PJ" and not INLINE_ABILITY_SKIP_RE.search(cleaned)


def _attack_title(title: str, attacks: list[StatAttack]) -> bool:
    return any(attack.name == title for attack in attacks) or bool(ATTACK_RE.search(title))


def _parse_ability_heuristics(text: str) -> list[StatAbility]:
    normalized = strip_layout_glyphs(text)
    if not normalized:
        return []
    abilities: list[StatAbility] = []
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if lines and STAT_ATTACK_LINE_RE.match(lines[0]):
        attack_title = lines[0].split("·", 1)[0].strip()
        attack_body = "\n".join(lines[1:]).strip()
        abilities.append(StatAbility(title=attack_title, text=attack_body))
    for pattern, title in ABILITY_BODY_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        body = normalized[match.start() :].strip()
        if not any(ability.title == title for ability in abilities):
            abilities.append(StatAbility(title=title, text=body))
    return abilities


def _parse_ability_block(text: str) -> StatAbility | None:
    lines = [line.strip() for line in strip_layout_glyphs(text).splitlines() if line.strip()]
    if not lines:
        return None
    first_match = ABILITY_TITLE_RE.match(lines[0])
    if not first_match:
        return None
    title = _normalize_ability_title(first_match.group(1))
    if not title or INLINE_ABILITY_SKIP_RE.search(title):
        return None
    body_parts: list[str] = []
    inline_body = first_match.group(2).strip()
    if inline_body:
        body_parts.append(inline_body)
    body_parts.extend(lines[1:])
    body = "\n".join(body_parts).strip()
    return StatAbility(title=title, text=body)


def _parse_abilities_from_inline_text(text: str) -> list[StatAbility]:
    normalized = strip_layout_glyphs(text)
    init_match = re.search(r"\(I\)\s*Init\.", normalized)
    search_text = normalized[init_match.end() :] if init_match else normalized
    matches = list(INLINE_ABILITY_TITLE_RE.finditer(search_text))
    abilities: list[StatAbility] = []
    for index, match in enumerate(matches):
        title = _normalize_ability_title(match.group(1))
        if not title or INLINE_ABILITY_SKIP_RE.search(title):
            continue
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(search_text)
        body = search_text[body_start:body_end].strip()
        abilities.append(StatAbility(title=title, text=body))
    return abilities


def _is_ability_body_continuation(
    block: LayoutBlock, previous: LayoutBlock | None
) -> bool:
    if previous is None or previous.metadata.get("stat_block_role") != "ability":
        return False
    text = _normalized(block)
    if not text or block.metadata.get("is_bold"):
        return False
    if _is_stats_line(text) or _has_nc(text) or _is_ability_block(block):
        return False
    if LIST_ITEM_MARKER_RE.match(text):
        return False
    return len(text) <= 400


LIST_ITEM_MARKER_RE = re.compile(r"^[\u2022\u25a0\uf0af]")


def _is_stat_continuation(
    block: LayoutBlock,
    page_blocks: list[LayoutBlock] | None = None,
    block_idx: int | None = None,
) -> bool:
    if (
        page_blocks is not None
        and block_idx is not None
        and _is_stat_header_block(block, page_blocks, block_idx)
    ):
        return False
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
        if ":" in text or STAT_ATTACK_LINE_RE.search(text) or STAT_ABILITY_HINT_RE.search(text):
            return True
    if re.match(r"^\d+ pour", text):
        return True
    if text.endswith(")") and len(text) <= 40:
        return True
    return len(text) <= 120 and not CHAPTER_RE.match(text) and not NUMBERED_HEADING_RE.match(text)


def _is_real_section_heading(block: LayoutBlock) -> bool:
    text = strip_layout_glyphs(block.text)
    if CHAPTER_RE.match(text):
        return True
    if NUMBERED_HEADING_RE.match(text) and block.metadata.get("is_bold"):
        return True
    return False


def _is_callout_interrupt_block(block: LayoutBlock) -> bool:
    text = _normalized(block)
    if not text or not block.metadata.get("is_bold"):
        return False
    return text.isupper() and len(text.split()) <= 4


def _page_has_unclaimed_abilities(
    blocks: list[LayoutBlock], start_idx: int
) -> bool:
    for candidate in blocks[start_idx:]:
        if _is_ability_block(candidate):
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
    if _is_callout_interrupt_block(block) and _page_has_unclaimed_abilities(
        page_blocks, idx + 1
    ):
        return False
    text = _normalized(block)
    if not text or _is_ability_block(block) or _is_stats_line(text):
        return False
    if block.metadata.get("is_bold"):
        font = block.metadata.get("max_font_size") or 0
        if font >= 12 and not text.isupper():
            if STAT_ATTACK_LINE_RE.search(text) or STAT_ABILITY_HINT_RE.search(text):
                return False
            if not STAT_BLOCK_BODY_RE.search(text):
                following = page_blocks[idx + 1 :]
                if any(_is_ability_block(candidate) for candidate in following):
                    return False
                return True
    return False


def _is_narrative_interrupt_block(
    block: LayoutBlock,
    page_blocks: list[LayoutBlock] | None = None,
    block_idx: int | None = None,
) -> bool:
    if (
        page_blocks is not None
        and block_idx is not None
        and _is_stat_header_block(block, page_blocks, block_idx)
    ):
        return False
    text = _normalized(block)
    if not text or _is_ability_block(block) or _is_stats_line(text):
        return False
    if _is_icon_prefixed_name(block) or _has_nc(text):
        return False
    if not block.metadata.get("is_bold"):
        return False
    if ":" in text or STAT_BLOCK_BODY_RE.search(text):
        return False
    if _extract_rulebook_reference(text):
        return False
    return len(text) <= 80


def _interleave_ability_groups(
    left_group: list[LayoutBlock],
    right_group: list[LayoutBlock],
) -> list[LayoutBlock]:
    ordered: list[LayoutBlock] = []
    right_index = 0
    for left_index, left_block in enumerate(left_group):
        ordered.append(left_block)
        if right_index < len(right_group):
            ordered.append(right_group[right_index])
            right_index += 1
    ordered.extend(right_group[right_index:])
    return ordered


def _ability_blocks_in_reading_order(span: StatBlockSpan) -> list[LayoutBlock]:
    abilities_in_scan_order = [
        block
        for block in span.blocks
        if block.metadata.get("stat_block_role") == "ability"
    ]
    if not abilities_in_scan_order:
        return []

    page_width = max(block.bbox.x1 for block in span.blocks) * 1.2
    layout_page = LayoutPage(
        page_number=span.page_start,
        width=page_width,
        height=1000.0,
        text="",
        blocks=[],
    )

    split_at: int | None = None
    first_side = column_side(abilities_in_scan_order[0], page_width)
    for index in range(1, len(abilities_in_scan_order)):
        if column_side(abilities_in_scan_order[index], page_width) != first_side:
            split_at = index
            break

    if split_at is not None:
        leading_group = abilities_in_scan_order[:split_at]
        trailing_group = abilities_in_scan_order[split_at:]
        leading_group.sort(
            key=lambda block: column_major_sort_key(layout_page, block)
        )
        trailing_group.sort(
            key=lambda block: column_major_sort_key(layout_page, block)
        )
        if (
            first_side == "right"
            and column_side(trailing_group[0], page_width) == "left"
        ):
            if len(trailing_group) < len(leading_group):
                return _interleave_ability_groups(trailing_group, leading_group)
            return trailing_group + leading_group

    abilities_in_scan_order.sort(
        key=lambda block: column_major_sort_key(layout_page, block)
    )
    return abilities_in_scan_order


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
        if not text or is_page_number_label(text):
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
                    if idx > 0 and not blocks[idx - 1].metadata.get("stat_block_id"):
                        prev = blocks[idx - 1]
                        prev_text = _normalized(prev)
                        header_text = _normalized(block)
                        if prev_text and prev_text in header_text:
                            prev.metadata["stat_block_id"] = span_id
                            prev.metadata["stat_block_role"] = "header"
                            span_blocks.append(prev)
                    block.metadata["stat_block_id"] = span_id
                    block.metadata["stat_block_role"] = "header"
                    span_blocks.append(block)
                    idx += 1
                    while idx < len(blocks):
                        nxt = blocks[idx]
                        if _is_icon_block(nxt):
                            if any(
                                block.metadata.get("stat_block_role") == "header"
                                for block in span_blocks
                            ):
                                flush_span(span_id, span_blocks)
                                pending_icons.append(nxt)
                                idx += 1
                                break
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "icon"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        if _ends_stat_block(nxt, blocks, idx):
                            if _is_callout_interrupt_block(nxt) and not _is_stat_header_block(
                                nxt, blocks, idx
                            ):
                                idx += 1
                                continue
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
                        if _is_ability_body_continuation(
                            nxt, span_blocks[-1] if span_blocks else None
                        ):
                            nxt.metadata["stat_block_id"] = span_id
                            nxt.metadata["stat_block_role"] = "ability"
                            span_blocks.append(nxt)
                            idx += 1
                            continue
                        if _is_narrative_interrupt_block(nxt, blocks, idx) and any(
                            _is_ability_block(candidate)
                            for candidate in blocks[idx + 1 :]
                        ):
                            idx += 1
                            continue
                        if _is_stat_continuation(nxt, blocks, idx) and span_blocks:
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
        normalized_combined = normalize_attack_separators(combined)
        name = ""
        subtitle: str | None = None
        nc: int | str | None = None
        attributes: dict[str, int] = {}
        abilities: list[StatAbility] = []

        for text in texts:
            if not text:
                continue
            header_match = NAME_NC_RE.search(text)
            if header_match:
                header_part = header_match.group(1).strip()
                nc = _parse_nc_value(header_match.group(2))
                if "," in header_part:
                    name_part, sub_part = header_part.split(",", 1)
                    name = name_part.strip()
                    subtitle = sub_part.strip()
                else:
                    name = header_part
            elif _has_nc(text):
                nc_match = NC_RE.search(text)
                if nc_match:
                    nc = _parse_nc_value(nc_match.group(1))
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

        for attr, sign, value in STATS_LINE_RE.findall(normalized_combined):
            key = attr.upper()
            if key in COF_ATTRIBUTES:
                attributes[key] = int(value) if sign == "+" else -int(value)

        combat_stats = _parse_combat_stats(normalized_combined)
        attacks = _parse_attacks(normalized_combined)

        for block in _ability_blocks_in_reading_order(span):
            ability = _parse_ability_block(self.normalize_block_text(block.text))
            if (
                ability
                and _valid_ability_title(ability.title)
                and not _attack_title(ability.title, attacks)
                and ability.title not in {a.title for a in abilities}
            ):
                abilities.append(ability)
            else:
                for ability in _parse_ability_heuristics(block.text):
                    if (
                        _valid_ability_title(ability.title)
                        and not _attack_title(ability.title, attacks)
                        and ability.title not in {a.title for a in abilities}
                    ):
                        abilities.append(ability)

        inline_abilities = _parse_abilities_from_inline_text(normalized_combined)
        if not abilities or len(abilities) < len(inline_abilities):
            for ability in inline_abilities:
                if (
                    _valid_ability_title(ability.title)
                    and not _attack_title(ability.title, attacks)
                    and ability.title not in {a.title for a in abilities}
                ):
                    abilities.append(ability)

        for ability in _parse_ability_heuristics(normalized_combined):
            if (
                _valid_ability_title(ability.title)
                and not _attack_title(ability.title, attacks)
                and ability.title not in {a.title for a in abilities}
            ):
                abilities.append(ability)

        if not name:
            for text in texts:
                candidate = text.strip()
                if candidate and ALL_CAPS_NAME_RE.match(candidate) and not _is_stats_line(candidate):
                    name = candidate.split(",")[0].strip()
                    break

        rulebook_reference = _extract_rulebook_reference(combined)
        abilities = [
            ability
            for ability in abilities
            if _valid_ability_title(ability.title) and not _attack_title(ability.title, attacks)
        ]

        block_refs = [
            BlockRef(page_number=block.page_number, block_index=block.block_index)
            for block in span.blocks
        ]
        return ParsedStatBlock(
            name=name,
            subtitle=subtitle,
            nc=nc,
            attributes=attributes,
            defense=combat_stats.get("defense"),
            vigor=combat_stats.get("vigor"),
            initiative=combat_stats.get("initiative"),
            mana=combat_stats.get("mana"),
            attacks=attacks,
            abilities=abilities,
            rulebook_reference=rulebook_reference,
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
