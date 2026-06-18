from __future__ import annotations

import functools
import re
from dataclasses import dataclass

import tiktoken

from rpg_ingest.raw.block_merging import is_wrap_around_pair
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, merge_block_bboxes
from rpg_ingest.raw.reading_order import (
    column_major_sort_key,
    column_side,
    find_block,
    heading_visual_tier,
    is_all_caps_heading_text,
    is_chapter_heading,
    is_credits_heading,
    is_editorial_credits_block,
    is_in_column_band,
    is_in_heading_content_zone,
    is_list_item_block,
    is_meta_box_heading,
    is_same_y_band,
    page_is_decorative_only,
    page_median_font,
    spatial_sort_key,
)
from rpg_core.stat_blocks.matching import enrich_chunk_metadata
from rpg_core.text.reflow import reflow_chunk_text
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.text_utils import strip_layout_glyphs
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord, SourceSpan
from rpg_core.storage.ids import chunk_id, page_block_id

DEFAULT_MAX_TOKENS = 1200
ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class _HeadingRef:
    section_index: int
    page_number: int
    block_index: int
    block: LayoutBlock
    title: str
    is_content_only: bool
    tier: str = "other"


@functools.lru_cache(maxsize=1)
def _get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def estimate_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _chunk_type_hint(
    text: str,
    blocks: list[LayoutBlock],
    *,
    profile: StatBlockProfile | None = None,
) -> str:
    if profile:
        hinted = profile.chunk_type_hint(text, blocks)
        if hinted:
            return hinted
    lowered = text.lower()
    if "secret" in lowered or "gm only" in lowered:
        return "secret"
    if "clue" in lowered:
        return "clue"
    if "handout" in lowered:
        return "handout"
    if "map" in lowered[:200]:
        return "map"
    return "lore"


def _section_accepts_editorial_credits(section: SectionRecord) -> bool:
    return is_credits_heading(section.title)


def _preface_page_numbers(
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
) -> list[int]:
    if heading_ref.tier != "meta" or is_credits_heading(heading_ref.title):
        return []
    previous_page = 0
    for ref in heading_refs:
        if ref.section_index == heading_ref.section_index:
            break
        previous_page = max(previous_page, ref.page_number)
    if heading_ref.page_number <= previous_page + 1:
        return []
    return list(range(previous_page + 1, heading_ref.page_number))


def _blocks_for_meta_preface(
    pages: list[LayoutPage],
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    heading_positions: set[tuple[int, int]],
    claimed: set[tuple[int, int]],
) -> list[tuple[LayoutPage, LayoutBlock]]:
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    heading = heading_ref.block
    for page_number in _preface_page_numbers(heading_ref, heading_refs):
        page = next((candidate for candidate in pages if candidate.page_number == page_number), None)
        if page is None:
            continue
        for block in page.blocks:
            pos = (page.page_number, block.block_index)
            if pos in claimed or pos in heading_positions:
                continue
            if is_editorial_credits_block(block):
                continue
            if not is_in_column_band(block, heading):
                continue
            result.append((page, block))
    return result


def _blocks_for_page_range(
    pages: list[LayoutPage], page_start: int, page_end: int
) -> list[tuple[LayoutPage, LayoutBlock]]:
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    for page in pages:
        if page.page_number < page_start or page.page_number > page_end:
            continue
        for block in page.blocks:
            result.append((page, block))
    return result


def _first_heading_y_on_page(
    page: LayoutPage, heading_positions: set[tuple[int, int]]
) -> float | None:
    ys = [
        block.bbox.y0
        for block in page.blocks
        if (page.page_number, block.block_index) in heading_positions
    ]
    return min(ys) if ys else None


def _first_heading_y_in_column(
    page: LayoutPage,
    heading_refs: list[_HeadingRef],
    side: str,
) -> float | None:
    ys = [
        ref.block.bbox.y0
        for ref in heading_refs
        if ref.page_number == page.page_number
        and column_side(ref.block, page.width) == side
    ]
    return min(ys) if ys else None


def _continuation_claims_block(
    block: LayoutBlock,
    page: LayoutPage,
    page_blocks: list[LayoutBlock],
    *,
    first_heading_y: float | None,
) -> bool:
    if first_heading_y is None or block.bbox.y0 >= first_heading_y:
        return True
    above = [candidate for candidate in page_blocks if candidate.bbox.y0 < first_heading_y]
    if not above:
        return False
    above.sort(key=spatial_sort_key)
    for first_above in above:
        if first_above.metadata.get("stat_block_id"):
            continue
        continuation_side = column_side(first_above, page.width)
        if is_same_y_band(block, first_above):
            return column_side(block, page.width) == continuation_side
        return column_side(block, page.width) == continuation_side
    return True


def _block_in_parallel_column(
    page: LayoutPage,
    heading: LayoutBlock,
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
    owner: _HeadingRef,
) -> bool:
    if owner.tier == "banner":
        return False
    if is_in_column_band(block, heading):
        return False
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if ref.section_index == owner.section_index:
            continue
        if is_in_column_band(block, ref.block):
            return False
    return True


def _first_chapter_heading_y_in_column(
    page: LayoutPage,
    heading_refs: list[_HeadingRef],
    side: str,
) -> float | None:
    ys = [
        ref.block.bbox.y0
        for ref in heading_refs
        if ref.page_number == page.page_number
        and column_side(ref.block, page.width) == side
        and is_chapter_heading(ref.title)
    ]
    return min(ys) if ys else None


def _parallel_blocked_by_column_owner(
    page: LayoutPage,
    block: LayoutBlock,
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    sections: list[SectionRecord],
    column_continuation_owners: dict[tuple[int, str], int] | None,
) -> bool:
    if not column_continuation_owners:
        return False
    col_side = column_side(block, page.width)
    owner = column_continuation_owners.get((page.page_number, col_side))
    if owner is None or owner == heading_ref.section_index:
        return False
    if sections[owner].page_start >= page.page_number:
        return False
    if any(
        ref.page_number == page.page_number
        and column_side(ref.block, page.width) == col_side
        for ref in heading_refs
    ):
        return False
    return True


def _parallel_subordinate_list_item(
    page: LayoutPage,
    heading: LayoutBlock,
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
    owner: _HeadingRef,
) -> bool:
    if owner.tier != "subordinate" or not is_list_item_block(block):
        return False
    if is_in_column_band(block, heading):
        return False
    side = column_side(block, page.width)
    chapter_y = _first_chapter_heading_y_in_column(page, heading_refs, side)
    if chapter_y is not None and block.bbox.y0 >= chapter_y:
        return False
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if ref.section_index == owner.section_index:
            continue
        if ref.tier != "subordinate":
            continue
        if is_in_column_band(block, ref.block):
            return False
    return True


def _parallel_subordinate_list_owner(
    page: LayoutPage,
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
) -> int | None:
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if _parallel_subordinate_list_item(
            page, ref.block, block, heading_refs, ref
        ):
            return ref.section_index
    return None


def _parallel_column_owner(
    page: LayoutPage,
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
) -> int | None:
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if ref.tier == "banner":
            continue
        if _block_in_parallel_column(page, ref.block, block, heading_refs, ref):
            return ref.section_index
    return None


def _same_page_heading_zone_owner(
    page: LayoutPage,
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
) -> int | None:
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if is_in_heading_content_zone(
            block, ref.block, heading_text=ref.title
        ):
            return ref.section_index
    return None


def _intervening_heading_blocks(
    heading: LayoutBlock,
    block: LayoutBlock,
    page: LayoutPage,
    heading_refs: list[_HeadingRef],
    *,
    owner: _HeadingRef,
    sections: list[SectionRecord],
) -> list[LayoutBlock]:
    between: list[LayoutBlock] = []
    owner_parent = sections[owner.section_index].parent_section_id
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if ref.block_index == heading.block_index and ref.page_number == heading.page_number:
            continue
        if (
            owner_parent is not None
            and sections[ref.section_index].parent_section_id == owner_parent
            and ref.section_index != owner.section_index
        ):
            if is_all_caps_heading_text(ref.title):
                continue
            if not is_in_column_band(ref.block, owner.block):
                continue
        other = ref.block
        if other.bbox.y0 <= heading.bbox.y0:
            continue
        if other.bbox.y0 >= block.bbox.y0:
            continue
        if is_in_heading_content_zone(block, other, heading_text=ref.title):
            between.append(other)
    return between


def _gap_pages_between(
    pages: list[LayoutPage], from_page: int, to_page: int
) -> list[LayoutPage]:
    return [
        page
        for page in pages
        if from_page < page.page_number < to_page and page_is_decorative_only(page)
    ]


def _last_text_page_before(
    pages: list[LayoutPage], page_number: int
) -> int | None:
    probe = page_number - 1
    while probe >= 1:
        page = next((p for p in pages if p.page_number == probe), None)
        if page is None:
            return None
        if page_is_decorative_only(page):
            probe -= 1
            continue
        return probe
    return None


def _opposite_column_wrap_owners(
    pages: list[LayoutPage],
    heading_refs: list[_HeadingRef],
    sections: list[SectionRecord],
    heading_positions: set[tuple[int, int]],
) -> dict[tuple[int, str], int]:
    """When a section ends a page in one column, COF2 layouts often continue on the next page in the other column."""
    owners: dict[tuple[int, str], int] = {}

    for ref in heading_refs:
        if ref.tier == "banner":
            continue
        heading_page = next(
            (page for page in pages if page.page_number == ref.page_number),
            None,
        )
        if heading_page is None:
            continue
        heading_side = column_side(ref.block, heading_page.width)
        opposite = "right" if heading_side == "left" else "left"
        has_body = any(
            block.bbox.y0 > ref.block.bbox.y0
            and column_side(block, heading_page.width) == heading_side
            and (ref.page_number, block.block_index) not in heading_positions
            and not is_editorial_credits_block(block)
            for block in heading_page.blocks
        )
        tail_heading = ref.block.bbox.y0 >= heading_page.height * 0.70
        if not has_body and not tail_heading:
            continue
        if any(
            other.page_number == ref.page_number
            and column_side(other.block, heading_page.width) == opposite
            and other.tier in {"chapter", "banner"}
            and other.block.bbox.y0 > ref.block.bbox.y0
            for other in heading_refs
        ):
            continue

        next_page_num = ref.page_number + 1
        next_page = next(
            (page for page in pages if page.page_number == next_page_num),
            None,
        )
        if next_page is None or page_is_decorative_only(next_page):
            continue
        if sections[ref.section_index].page_end < next_page_num:
            continue
        if any(
            other.page_number == next_page_num
            and column_side(other.block, next_page.width) == opposite
            and other.tier == "chapter"
            for other in heading_refs
        ):
            continue

        key = (next_page_num, opposite)
        existing = owners.get(key)
        if existing is None:
            owners[key] = ref.section_index
        elif sections[ref.section_index].page_start > sections[existing].page_start:
            owners[key] = ref.section_index

    return owners


def _has_subordinate_heading_below_in_column(
    ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    page: LayoutPage,
) -> bool:
    heading_side = column_side(ref.block, page.width)
    for other in heading_refs:
        if other.section_index == ref.section_index:
            continue
        if other.page_number != ref.page_number:
            continue
        if other.tier != "subordinate":
            continue
        if column_side(other.block, page.width) != heading_side:
            continue
        if other.block.bbox.y0 > ref.block.bbox.y0:
            return True
    return False


def _column_continuation_owner_priority(
    candidate: _HeadingRef,
    incumbent_index: int,
    heading_refs: list[_HeadingRef],
    sections: list[SectionRecord],
) -> bool:
    """True when candidate should replace incumbent for same (page, column) continuation."""
    incumbent = heading_refs[incumbent_index]
    if sections[candidate.section_index].page_start > sections[incumbent_index].page_start:
        return True
    if sections[candidate.section_index].page_start < sections[incumbent_index].page_start:
        return False
    if candidate.tier == "subordinate" and incumbent.tier in {"chapter", "banner"}:
        return True
    if incumbent.tier == "subordinate" and candidate.tier in {"chapter", "banner"}:
        return False
    return False


def _column_continuation_owners(
    pages: list[LayoutPage],
    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]],
    heading_refs: list[_HeadingRef],
    sections: list[SectionRecord],
    heading_positions: set[tuple[int, int]],
) -> dict[tuple[int, str], int]:
    owners: dict[tuple[int, str], int] = {}

    for page in pages:
        if page_is_decorative_only(page):
            continue
        if any(is_editorial_credits_block(block) for block in page.blocks):
            continue
        last_text_page = _last_text_page_before(pages, page.page_number)
        if last_text_page is None:
            continue

        for side in ("left", "right"):
            best_index: int | None = None
            best_y = -1.0
            for section_index, block_items in enumerate(section_blocks):
                prev_blocks = [
                    block
                    for pg, block in block_items
                    if pg.page_number == last_text_page
                    and column_side(block, pg.width) == side
                ]
                if not prev_blocks:
                    continue
                last_y = max(block.bbox.y1 for block in prev_blocks)
                if last_y > best_y:
                    best_y = last_y
                    best_index = section_index

            if best_index is None:
                continue
            if sections[best_index].page_end < last_text_page:
                continue

            if any(
                ref.page_number == page.page_number
                and column_side(ref.block, page.width) == side
                and ref.tier == "chapter"
                for ref in heading_refs
            ):
                continue

            owners[(page.page_number, side)] = best_index

    for ref in heading_refs:
        if ref.tier == "banner":
            continue
        heading_page = next(
            (page for page in pages if page.page_number == ref.page_number),
            None,
        )
        if heading_page is None:
            continue
        if ref.tier in {"chapter", "banner"} and _has_subordinate_heading_below_in_column(
            ref, heading_refs, heading_page
        ):
            continue
        heading_side = column_side(ref.block, heading_page.width)
        for page in pages:
            if page.page_number <= ref.page_number:
                continue
            if page_is_decorative_only(page):
                continue
            last_text_page = _last_text_page_before(pages, page.page_number)
            if last_text_page is None or last_text_page < ref.page_number:
                continue
            key = (page.page_number, heading_side)
            existing = owners.get(key)
            if existing is None:
                owners[key] = ref.section_index
            elif _column_continuation_owner_priority(
                ref, existing, heading_refs, sections
            ):
                owners[key] = ref.section_index

    for key, section_index in _opposite_column_wrap_owners(
        pages, heading_refs, sections, heading_positions
    ).items():
        page_num, _side = key
        existing = owners.get(key)
        if existing is None:
            owners[key] = section_index
            continue
        wrap_ref = heading_refs[section_index]
        if wrap_ref.page_number == page_num - 1:
            owners[key] = section_index
            continue
        if sections[section_index].page_start > sections[existing].page_start:
            owners[key] = section_index
        elif sections[section_index].page_start == sections[existing].page_start:
            candidate_tier = heading_refs[section_index].tier
            incumbent_tier = heading_refs[existing].tier
            if candidate_tier in {"chapter", "banner"} and incumbent_tier == "subordinate":
                owners[key] = section_index
            elif candidate_tier == "subordinate" and incumbent_tier in {"chapter", "banner"}:
                pass
            elif section_index > existing:
                owners[key] = section_index

    return owners


def _block_in_subordinate_wrap_zone(
    page: LayoutPage,
    heading: LayoutBlock,
    block: LayoutBlock,
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    *,
    profile: StatBlockProfile | None = None,
) -> bool:
    if heading_ref.tier != "subordinate":
        return False
    if block.bbox.y0 >= heading.bbox.y0:
        return False
    if block.bbox.x0 >= page.width * 0.5:
        return False
    nearest_above = _nearest_heading_y_above_block(block, heading_refs, page)
    if block.bbox.y0 <= nearest_above:
        return False
    for other in page.blocks:
        if other is block:
            continue
        if other.bbox.x0 < page.width * 0.5:
            continue
        if is_wrap_around_pair(
            block,
            other,
            page_width=page.width,
            page_blocks=page.blocks,
            profile=profile,
        ):
            return True
    if (
        heading.bbox.y0 >= page.height * 0.65
        and block.bbox.y0 > page.height * 0.30
        and block.bbox.x1 > page.width * 0.55
    ):
        return True
    return False


def _nearest_heading_y_above_block(
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
    page: LayoutPage,
) -> float:
    best = 0.0
    for other in heading_refs:
        if other.page_number != page.page_number:
            continue
        if other.block.bbox.y0 < block.bbox.y0 and other.block.bbox.y0 > best:
            best = other.block.bbox.y0
    return best


def _reserved_for_subordinate_heading(
    page: LayoutPage,
    block: LayoutBlock,
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    *,
    profile: StatBlockProfile | None = None,
) -> bool:
    if heading_ref.tier == "subordinate":
        return False
    for other in heading_refs:
        if other.page_number != page.page_number:
            continue
        if other.tier != "subordinate":
            continue
        if other.block.bbox.y0 <= heading_ref.block.bbox.y0:
            continue
        if _block_in_subordinate_wrap_zone(
            page,
            other.block,
            block,
            other,
            heading_refs,
            profile=profile,
        ):
            return True
    return False


def _blocks_for_section_spatial(
    pages: list[LayoutPage],
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    heading_positions: set[tuple[int, int]],
    sections: list[SectionRecord],
    *,
    continuation_by_page: dict[int, int | None],
    column_continuation_owners: dict[tuple[int, str], int] | None = None,
    claimed: set[tuple[int, int]] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[tuple[LayoutPage, LayoutBlock]]:
    heading = heading_ref.block
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    taken = claimed or set()

    for page in pages:
        if page.page_number < heading_ref.page_number:
            continue
        for block in page.blocks:
            pos = (page.page_number, block.block_index)
            if pos in taken:
                continue
            if (
                heading_ref.is_content_only
                and pos == (heading_ref.page_number, heading_ref.block_index)
            ):
                result.append((page, block))
                continue
            if pos in heading_positions:
                continue
            if (
                is_editorial_credits_block(block)
                and not _section_accepts_editorial_credits(sections[heading_ref.section_index])
            ):
                continue

            if page.page_number == heading_ref.page_number:
                if _reserved_for_subordinate_heading(
                    page,
                    block,
                    heading_ref,
                    heading_refs,
                    profile=profile,
                ):
                    continue
                if _section_accepts_editorial_credits(sections[heading_ref.section_index]):
                    if (
                        block.bbox.y0 > heading.bbox.y0
                        and is_in_column_band(block, heading)
                    ):
                        result.append((page, block))
                        continue
                in_zone = is_in_heading_content_zone(
                    block, heading, heading_text=heading_ref.title
                )
                in_parallel = _block_in_parallel_column(
                    page, heading, block, heading_refs, heading_ref
                )
                in_parallel_list = _parallel_subordinate_list_item(
                    page, heading, block, heading_refs, heading_ref
                )
                in_wrap_zone = _block_in_subordinate_wrap_zone(
                    page,
                    heading,
                    block,
                    heading_ref,
                    heading_refs,
                    profile=profile,
                )
                preserve_parallel_list = in_parallel_list
                col_owner_blocked = _parallel_blocked_by_column_owner(
                    page,
                    block,
                    heading_ref,
                    heading_refs,
                    sections,
                    column_continuation_owners,
                )
                if col_owner_blocked:
                    in_parallel = False
                    if not preserve_parallel_list:
                        in_parallel_list = False
                elif column_continuation_owners:
                    col_side = column_side(block, page.width)
                    owner = column_continuation_owners.get(
                        (page.page_number, col_side)
                    )
                    if (
                        owner is not None
                        and owner != heading_ref.section_index
                    ):
                        in_parallel = False
                        if not preserve_parallel_list:
                            in_parallel_list = False
                if not heading_ref.is_content_only and block.bbox.y0 <= heading.bbox.y0:
                    if (
                        not in_parallel
                        and not in_parallel_list
                        and not in_zone
                        and not in_wrap_zone
                    ):
                        continue
                if (
                    not in_zone
                    and not in_parallel
                    and not in_parallel_list
                    and not in_wrap_zone
                ):
                    continue
                if (in_zone or in_parallel_list) and _intervening_heading_blocks(
                    heading,
                    block,
                    page,
                    heading_refs,
                    owner=heading_ref,
                    sections=sections,
                ):
                    continue
            else:
                if (
                    heading_ref.tier == "meta"
                    and is_credits_heading(heading_ref.title)
                ):
                    continue
                last_text_page = _last_text_page_before(pages, page.page_number)
                gap_pages = (
                    _gap_pages_between(pages, last_text_page, page.page_number)
                    if last_text_page is not None
                    else []
                )
                col_side = column_side(block, page.width)
                column_first_heading_y = _first_heading_y_in_column(
                    page, heading_refs, col_side
                )
                page_first_heading_y = _first_heading_y_on_page(
                    page, heading_positions
                )
                column_owner = (
                    column_continuation_owners or {}
                ).get((page.page_number, col_side))
                is_sparse_continuation = (
                    continuation_by_page.get(page.page_number) == heading_ref.section_index
                    and bool(gap_pages)
                    and (
                        page_first_heading_y is None
                        or block.bbox.y0 < page_first_heading_y
                    )
                )
                sparse_owner = continuation_by_page.get(page.page_number)
                is_column_continuation = (
                    column_owner == heading_ref.section_index
                    and (
                        column_first_heading_y is None
                        or block.bbox.y0 < column_first_heading_y
                    )
                )
                if (
                    sparse_owner is not None
                    and sparse_owner != heading_ref.section_index
                    and bool(gap_pages)
                ):
                    is_column_continuation = False
                if is_column_continuation:
                    for ref in heading_refs:
                        if ref.page_number != page.page_number:
                            continue
                        if ref.section_index == heading_ref.section_index:
                            continue
                        if ref.tier != "subordinate":
                            continue
                        if ref.block.bbox.y0 >= block.bbox.y0:
                            continue
                        if _block_in_parallel_column(
                            page, ref.block, block, heading_refs, ref
                        ):
                            is_column_continuation = False
                            break
                if not is_sparse_continuation and not is_column_continuation:
                    continue
                parallel_list_owner = _parallel_subordinate_list_owner(
                    page, block, heading_refs
                )
                if (
                    parallel_list_owner is not None
                    and parallel_list_owner != heading_ref.section_index
                    and not is_sparse_continuation
                ):
                    continue
                zone_owner = _same_page_heading_zone_owner(page, block, heading_refs)
                if (
                    zone_owner is not None
                    and zone_owner != heading_ref.section_index
                    and is_column_continuation
                    and not is_sparse_continuation
                ):
                    continue
                if not _continuation_claims_block(
                    block,
                    page,
                    page.blocks,
                    first_heading_y=column_first_heading_y
                    if column_first_heading_y is not None
                    else page_first_heading_y,
                ):
                    continue
                if _intervening_heading_blocks(
                    heading,
                    block,
                    page,
                    heading_refs,
                    owner=heading_ref,
                    sections=sections,
                ):
                    continue

            result.append((page, block))

    result.sort(key=lambda item: column_major_sort_key(item[0], item[1]))
    return result


def _nearest_heading_ref(
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
    *,
    page_width: float | None = None,
) -> _HeadingRef | None:
    if page_width is None:
        page_width = max(
            (ref.block.bbox.x1 for ref in heading_refs),
            default=510.0,
        ) * 1.2
    block_key = spatial_sort_key(block)
    block_side = column_side(block, page_width)

    def _pick_best(candidates: list[_HeadingRef]) -> _HeadingRef | None:
        best: _HeadingRef | None = None
        best_key: tuple[int, float, float] | None = None
        for ref in candidates:
            ref_key = spatial_sort_key(ref.block)
            if ref_key > block_key:
                continue
            if best is None or ref_key > best_key:
                best = ref
                best_key = ref_key
        return best

    same_column = [
        ref
        for ref in heading_refs
        if column_side(ref.block, page_width) == block_side
    ]
    best = _pick_best(same_column)
    if best is not None:
        return best
    return _pick_best(list(heading_refs))


def _assign_orphan_blocks(
    pages: list[LayoutPage],
    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]],
    heading_refs: list[_HeadingRef],
    heading_positions: set[tuple[int, int]],
    claimed: set[tuple[int, int]],
    sections: list[SectionRecord],
) -> None:
    for page in pages:
        for block in page.blocks:
            pos = (page.page_number, block.block_index)
            if pos in claimed or pos in heading_positions:
                continue
            if is_editorial_credits_block(block):
                continue
            parallel_owner: _HeadingRef | None = None
            for ref in heading_refs:
                if ref.page_number != page.page_number:
                    continue
                if _block_in_parallel_column(
                    page, ref.block, block, heading_refs, ref
                ):
                    parallel_owner = ref
                    break
            if parallel_owner is not None:
                section_blocks[parallel_owner.section_index].append((page, block))
                claimed.add(pos)
                continue
            nearest = _nearest_heading_ref(
                block, heading_refs, page_width=page.width
            )
            if nearest is None:
                continue
            if is_credits_heading(sections[nearest.section_index].title):
                forward_refs = [
                    ref
                    for ref in heading_refs
                    if (ref.page_number, ref.block.bbox.y0)
                    > (block.page_number, block.bbox.y0)
                ]
                if forward_refs:
                    nearest = min(
                        forward_refs,
                        key=lambda ref: (ref.page_number, ref.block.bbox.y0),
                    )
            section_blocks[nearest.section_index].append((page, block))
            claimed.add(pos)


def _continuation_owner_by_page(
    pages: list[LayoutPage],
    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]],
) -> dict[int, int | None]:
    owners: dict[int, int | None] = {}
    for page in pages:
        if page_is_decorative_only(page):
            continue
        if any(is_editorial_credits_block(block) for block in page.blocks):
            continue
        last_text_page = _last_text_page_before(pages, page.page_number)
        if last_text_page is None:
            continue
        gap_pages = _gap_pages_between(pages, last_text_page, page.page_number)
        if not gap_pages:
            continue

        best_index: int | None = None
        best_y = -1.0
        for section_index, block_items in enumerate(section_blocks):
            prev_blocks = [
                block for pg, block in block_items if pg.page_number == last_text_page
            ]
            if not prev_blocks:
                continue
            last_y = max(block.bbox.y1 for block in prev_blocks)
            if last_y > best_y:
                best_y = last_y
                best_index = section_index
        owners[page.page_number] = best_index

    return owners


def chunk_block_signature(chunk: ChunkRecord) -> frozenset[str]:
    block_ids: list[str] = []
    for span in chunk.source_spans:
        block_ids.extend(span.page_block_ids)
    return frozenset(block_ids)


def _chunk_block_count(chunk: ChunkRecord) -> int:
    return sum(len(span.page_block_ids) for span in chunk.source_spans)


def _stat_block_header_position(
    pages: list[LayoutPage], stat_id: str
) -> tuple[int, int] | None:
    for page in pages:
        for block in page.blocks:
            if (
                block.metadata.get("stat_block_id") == stat_id
                and block.metadata.get("stat_block_role") == "header"
            ):
                return (page.page_number, block.block_index)
    return None


def _chunk_contains_position(chunk: ChunkRecord, pos: tuple[int, int]) -> bool:
    page_num, block_idx = pos
    target_id = page_block_id(chunk.document_id, page_num, block_idx)
    return any(target_id in span.page_block_ids for span in chunk.source_spans)


def _resolve_stat_block_section_id(
    pages: list[LayoutPage],
    sections: list[SectionRecord],
    header_pos: tuple[int, int],
    default_section_id: str | None,
) -> str | None:
    page_num, header_idx = header_pos
    page = next((p for p in pages if p.page_number == page_num), None)
    if page is None:
        return default_section_id

    header_block = next((b for b in page.blocks if b.block_index == header_idx), None)
    if header_block is None:
        return default_section_id

    header_side = column_side(header_block, page.width)
    preceding_text_parts: list[str] = []
    for block in page.blocks:
        if block.block_index >= header_idx:
            continue
        if column_side(block, page.width) != header_side:
            continue
        if block.metadata.get("stat_block_role") == "header":
            continue
        preceding_text_parts.append(strip_layout_glyphs(block.text))

    preceding_text = " ".join(preceding_text_parts).lower()
    if not preceding_text.strip():
        return default_section_id

    best_section: SectionRecord | None = None
    best_score = 0
    for section in sections:
        if section.page_start > page_num or section.page_end < page_num:
            continue
        title_norm = strip_layout_glyphs(section.title).lower()
        if title_norm and title_norm in preceding_text:
            score = len(title_norm) + 10
            if score > best_score:
                best_score = score
                best_section = section
            continue
        words = [word for word in re.split(r"\W+", title_norm) if len(word) >= 3]
        if not words:
            continue
        matched = sum(1 for word in words if word in preceding_text)
        if matched >= min(2, len(words)) and matched > best_score:
            best_score = matched
            best_section = section

    return best_section.id if best_section else default_section_id


def _reassign_stat_block_sections(
    chunks: list[ChunkRecord],
    pages: list[LayoutPage],
    sections: list[SectionRecord],
) -> list[ChunkRecord]:
    result: list[ChunkRecord] = []
    for chunk in chunks:
        if chunk.chunk_type_hint != "stat_block":
            result.append(chunk)
            continue
        span_id = chunk.metadata.get("stat_block_span_id")
        if not span_id:
            result.append(chunk)
            continue
        header_pos = _stat_block_header_position(pages, span_id)
        if not header_pos:
            result.append(chunk)
            continue
        new_section_id = _resolve_stat_block_section_id(
            pages, sections, header_pos, chunk.section_id
        )
        if new_section_id != chunk.section_id:
            result.append(chunk.model_copy(update={"section_id": new_section_id}))
        else:
            result.append(chunk)
    return result


def _finalize_chunks(
    chunks: list[ChunkRecord],
    pages: list[LayoutPage],
    sections: list[SectionRecord],
) -> list[ChunkRecord]:
    return _reassign_stat_block_sections(
        _deduplicate_stat_block_chunks(chunks, pages),
        pages,
        sections,
    )


def _deduplicate_stat_block_chunks(
    chunks: list[ChunkRecord],
    pages: list[LayoutPage],
) -> list[ChunkRecord]:
    by_span: dict[str, list[ChunkRecord]] = {}
    result: list[ChunkRecord] = []

    for chunk in chunks:
        if chunk.chunk_type_hint != "stat_block":
            result.append(chunk)
            continue
        span_id = chunk.metadata.get("stat_block_span_id")
        if not span_id:
            result.append(chunk)
            continue
        by_span.setdefault(span_id, []).append(chunk)

    for span_id, group in by_span.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        winner = max(group, key=_chunk_block_count)
        header_pos = _stat_block_header_position(pages, span_id)
        if header_pos:
            header_chunk = next(
                (chunk for chunk in group if _chunk_contains_position(chunk, header_pos)),
                None,
            )
            if header_chunk and header_chunk.section_id:
                winner = winner.model_copy(update={"section_id": header_chunk.section_id})
        result.append(winner)

    return result


def chunk_uniqueness_stats(chunks: list[ChunkRecord]) -> dict[str, float | int]:
    if not chunks:
        return {
            "chunk_unique_block_signature_count": 0,
            "duplicate_chunk_count": 0,
            "chunk_unique_block_signature_ratio": 1.0,
        }
    signatures = [chunk_block_signature(chunk) for chunk in chunks]
    unique_count = len(set(signatures))
    return {
        "chunk_unique_block_signature_count": unique_count,
        "duplicate_chunk_count": len(chunks) - unique_count,
        "chunk_unique_block_signature_ratio": unique_count / len(chunks),
    }


def _partition_by_stat_boundaries(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
) -> list[tuple[str | None, list[tuple[LayoutPage, LayoutBlock]]]]:
    groups: list[tuple[str | None, list[tuple[LayoutPage, LayoutBlock]]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    current_stat_id: str | None = None

    for page, block in block_items:
        stat_id = block.metadata.get("stat_block_id")
        if current and stat_id != current_stat_id:
            groups.append((current_stat_id, current))
            current = []
        current_stat_id = stat_id
        current.append((page, block))

    if current:
        groups.append((current_stat_id, current))
    return groups


def _split_at_page_gaps(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    pages: list[LayoutPage],
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    if not block_items:
        return []
    pages_by_number = {page.page_number: page for page in pages}
    groups: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    last_page: int | None = None
    for page, block in block_items:
        if current and last_page is not None and page.page_number > last_page + 1:
            gap_is_substantive = any(
                not page_is_decorative_only(pages_by_number[page_num])
                for page_num in range(last_page + 1, page.page_number)
                if page_num in pages_by_number
            )
            if gap_is_substantive:
                groups.append(current)
                current = []
        current.append((page, block))
        last_page = page.page_number
    if current:
        groups.append(current)
    return groups


def _split_blocks_into_chunks(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    max_tokens: int,
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    chunks: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    current_tokens = 0

    for page, block in block_items:
        block_tokens = estimate_tokens(block.text)
        if current and current_tokens + block_tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append((page, block))
        current_tokens += block_tokens

    if current:
        chunks.append(current)
    return chunks


def _split_at_heading_boundaries(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    heading_positions: set[tuple[int, int]],
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    groups: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    for page, block in block_items:
        pos = (page.page_number, block.block_index)
        if current and pos in heading_positions:
            groups.append(current)
            current = []
        current.append((page, block))
    if current:
        groups.append(current)
    return groups


def _split_at_subordinate_heading_boundaries(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    heading_refs: list[_HeadingRef],
    *,
    section_index: int,
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    if not block_items:
        return []
    groups: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    for page, block in block_items:
        if current:
            prev_page, prev_block = current[-1]
            for ref in heading_refs:
                if ref.section_index == section_index:
                    continue
                if ref.tier != "subordinate":
                    continue
                if ref.page_number != page.page_number:
                    continue
                if ref.block.bbox.y0 <= prev_block.bbox.y0:
                    continue
                if ref.block.bbox.y0 >= block.bbox.y0:
                    continue
                if is_in_column_band(block, ref.block):
                    groups.append(current)
                    current = []
                    break
        current.append((page, block))
    if current:
        groups.append(current)
    return groups if groups else [block_items]


def _group_blocks_for_chunking(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    max_tokens: int,
    heading_positions: set[tuple[int, int]] | None = None,
    heading_refs: list[_HeadingRef] | None = None,
    section_index: int | None = None,
    pages: list[LayoutPage] | None = None,
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    groups: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    for stat_id, stat_group in _partition_by_stat_boundaries(block_items):
        if stat_id:
            groups.append(stat_group)
        else:
            segments = (
                _split_at_heading_boundaries(stat_group, heading_positions)
                if heading_positions
                else [stat_group]
            )
            if heading_refs is not None and section_index is not None:
                segments = [
                    sub_segment
                    for segment in segments
                    for sub_segment in _split_at_subordinate_heading_boundaries(
                        segment,
                        heading_refs,
                        section_index=section_index,
                    )
                ]
            for segment in segments:
                if pages:
                    page_segments = _split_at_page_gaps(segment, pages)
                else:
                    page_segments = [segment]
                for page_segment in page_segments:
                    groups.extend(_split_blocks_into_chunks(page_segment, max_tokens))
    return groups


def _expand_stat_block_group(
    block_groups: list[tuple[LayoutPage, LayoutBlock]],
    stat_spans: dict[str, StatBlockSpan],
    pages: list[LayoutPage],
) -> list[tuple[LayoutPage, LayoutBlock]]:
    stat_id = next(
        (
            block.metadata.get("stat_block_id")
            for _, block in block_groups
            if block.metadata.get("stat_block_id")
        ),
        None,
    )
    if not stat_id or stat_id not in stat_spans:
        return block_groups
    pages_by_number = {page.page_number: page for page in pages}
    existing = {(page.page_number, block.block_index) for page, block in block_groups}
    expanded = list(block_groups)
    for block in stat_spans[stat_id].blocks:
        pos = (block.page_number, block.block_index)
        if pos in existing:
            continue
        page = pages_by_number.get(block.page_number)
        if page is None:
            continue
        expanded.append((page, block))
        existing.add(pos)
    expanded.sort(key=lambda item: column_major_sort_key(item[0], item[1]))
    return expanded


def _make_chunk(
    *,
    campaign_id: str,
    document_id: str,
    section_id: str | None,
    index: int,
    block_groups: list[tuple[LayoutPage, LayoutBlock]],
    needs_rechunk: bool = False,
    profile: StatBlockProfile | None = None,
    stat_spans: dict[str, StatBlockSpan] | None = None,
) -> ChunkRecord:
    blocks_only = [b for _, b in block_groups]
    stat_id = blocks_only[0].metadata.get("stat_block_id") if blocks_only else None
    metadata: dict = {}
    text: str

    if stat_id and profile and stat_spans and stat_id in stat_spans:
        parsed = profile.parse_span(stat_spans[stat_id])
        text = parsed.raw_text or "\n\n".join(
            profile.normalize_block_text(block.text) for _, block in block_groups
        )
        metadata = enrich_chunk_metadata(
            {
                "stat_block": parsed.model_dump(),
                "game_system": parsed.game_system,
                "stat_block_span_id": stat_id,
            }
        )
        chunk_hint = "stat_block"
    else:
        text = "\n\n".join(block.text for _, block in block_groups)
        chunk_hint = _chunk_type_hint(text, blocks_only, profile=profile)

    text = reflow_chunk_text(text)

    page_numbers = [page.page_number for page, _ in block_groups]
    page_start = min(page_numbers)
    page_end = max(page_numbers)

    spans_by_page: dict[int, list[LayoutBlock]] = {}
    for page, block in block_groups:
        spans_by_page.setdefault(page.page_number, []).append(block)

    source_spans: list[SourceSpan] = []
    for page_num in sorted(spans_by_page):
        page_blocks = spans_by_page[page_num]
        source_spans.append(
            SourceSpan(
                page=page_num,
                page_block_ids=[
                    page_block_id(document_id, page_num, b.block_index)
                    for b in page_blocks
                ],
                bbox=merge_block_bboxes(page_blocks),
            )
        )

    return ChunkRecord(
        id=chunk_id(document_id, page_start, index),
        campaign_id=campaign_id,
        document_id=document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        text=text,
        chunk_type_hint=chunk_hint,
        token_count=estimate_tokens(text),
        source_spans=source_spans,
        metadata=metadata,
        needs_rechunk=needs_rechunk,
    )


def build_chunks(
    pages: list[LayoutPage],
    sections: list[SectionRecord],
    *,
    campaign_id: str,
    document_id: str,
    heading_anchors: list[tuple[int, int]] | None = None,
    content_only_section_ids: frozenset[str] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stat_spans: list[StatBlockSpan] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[ChunkRecord]:
    if not pages:
        return []

    span_by_id = {span.id: span for span in (stat_spans or [])}
    chunks: list[ChunkRecord] = []
    chunk_index = 0
    content_only = content_only_section_ids or frozenset()

    if len(sections) <= 1 and sections[0].title == "Document":
        block_items = _blocks_for_page_range(
            pages, sections[0].page_start, sections[0].page_end
        )
        for group in _group_blocks_for_chunking(block_items, max_tokens, None):
            expanded_group = _expand_stat_block_group(group, span_by_id, pages)
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=sections[0].id,
                    index=chunk_index,
                    block_groups=expanded_group,
                    needs_rechunk=len(group) < 2,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1
        return _finalize_chunks(chunks, pages, sections)

    use_anchors = (
        heading_anchors is not None and len(heading_anchors) == len(sections)
    )

    if not use_anchors:
        for section in sections:
            block_items = _blocks_for_page_range(
                pages, section.page_start, section.page_end
            )
            if not block_items:
                continue
            groups = _group_blocks_for_chunking(block_items, max_tokens, None)
            for group in groups:
                expanded_group = _expand_stat_block_group(group, span_by_id, pages)
                chunks.append(
                    _make_chunk(
                        campaign_id=campaign_id,
                        document_id=document_id,
                        section_id=section.id,
                        index=chunk_index,
                        block_groups=expanded_group,
                        needs_rechunk=len(groups) == 1 and len(group) > 40,
                        profile=profile,
                        stat_spans=span_by_id,
                    )
                )
                chunk_index += 1
        return _finalize_chunks(chunks, pages, sections)

    heading_positions = set(heading_anchors)
    content_only_anchors = {
        anchor
        for section, anchor in zip(sections, heading_anchors, strict=True)
        if section.id in content_only
    }
    chunk_split_positions = heading_positions - content_only_anchors
    heading_refs: list[_HeadingRef] = []
    for section_index, (page_num, block_idx) in enumerate(heading_anchors):
        block = find_block(pages, page_num, block_idx)
        if block is None:
            continue
        page = next(p for p in pages if p.page_number == page_num)
        median = page_median_font(page.blocks)
        tier = heading_visual_tier(
            sections[section_index].title,
            block,
            median_font=median,
            page=page,
        )
        heading_refs.append(
            _HeadingRef(
                section_index=section_index,
                page_number=page_num,
                block_index=block_idx,
                block=block,
                title=sections[section_index].title,
                is_content_only=sections[section_index].id in content_only,
                tier=tier,
            )
        )

    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]] = [[] for _ in sections]
    claimed: set[tuple[int, int]] = set()
    sorted_refs = sorted(heading_refs, key=lambda ref: spatial_sort_key(ref.block))

    for ref in sorted_refs:
        incremental_column_owners = _column_continuation_owners(
            pages, section_blocks, heading_refs, sections, heading_positions
        )
        same_page_blocks = _blocks_for_section_spatial(
            pages,
            ref,
            heading_refs,
            heading_positions,
            sections,
            continuation_by_page={},
            column_continuation_owners=incremental_column_owners,
            claimed=claimed,
            profile=profile,
        )
        preface_blocks = _blocks_for_meta_preface(
            pages,
            ref,
            heading_refs,
            heading_positions,
            claimed,
        )
        section_blocks[ref.section_index].extend(preface_blocks)
        for page, block in preface_blocks:
            claimed.add((page.page_number, block.block_index))
        section_blocks[ref.section_index].extend(same_page_blocks)
        for page, block in same_page_blocks:
            claimed.add((page.page_number, block.block_index))

    column_owners = _column_continuation_owners(
        pages, section_blocks, heading_refs, sections, heading_positions
    )
    continuation_by_page = _continuation_owner_by_page(pages, section_blocks)
    for ref in sorted_refs:
        continuation_blocks = _blocks_for_section_spatial(
            pages,
            ref,
            heading_refs,
            heading_positions,
            sections,
            continuation_by_page=continuation_by_page,
            column_continuation_owners=column_owners,
            claimed=claimed,
            profile=profile,
        )
        section_blocks[ref.section_index].extend(continuation_blocks)
        for page, block in continuation_blocks:
            claimed.add((page.page_number, block.block_index))

    _assign_orphan_blocks(
        pages, section_blocks, heading_refs, heading_positions, claimed, sections
    )
    for block_items in section_blocks:
        block_items.sort(key=lambda item: column_major_sort_key(item[0], item[1]))

    for section_index, section in enumerate(sections):
        block_items = section_blocks[section_index]
        if not block_items:
            continue
        groups = _group_blocks_for_chunking(
            block_items,
            max_tokens,
            chunk_split_positions,
            heading_refs=heading_refs,
            section_index=section_index,
            pages=pages,
        )
        for group in groups:
            expanded_group = _expand_stat_block_group(group, span_by_id, pages)
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=section.id,
                    index=chunk_index,
                    block_groups=expanded_group,
                    needs_rechunk=len(groups) == 1 and len(group) > 40,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1

    return _finalize_chunks(chunks, pages, sections)
