from __future__ import annotations

import re
from dataclasses import dataclass, field

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_assistant.ingestion.raw.reading_order import (
    is_decorative_spread_title,
    is_page_number_label_block,
    is_spread_title_pair,
    is_vertical_running_header,
    page_median_font,
)

DRM_EMAIL_ORDER_RE = re.compile(
    r"\S+@\S+\.\S+.*\d{6}/\d+/\d+|\d{6}/\d+/\d+.*\S+@\S+\.\S+",
    re.IGNORECASE,
)
DRM_NAME_EMAIL_RE = re.compile(
    r"^\S+(?:\s+\S+)*\s*[-–]\s*\S+@\S+\.\S+",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\S+@\S+\.\S+", re.IGNORECASE)


@dataclass
class WatermarkFilterConfig:
    min_page_ratio: float = 0.5
    min_page_count: int = 3
    max_block_length: int = 200
    long_text_threshold: int = 80
    header_margin_ratio: float = 0.08
    footer_margin_ratio: float = 0.08
    max_removed_patterns: int = 10
    extra_patterns: list[re.Pattern[str]] = field(default_factory=list)


@dataclass
class WatermarkFilterResult:
    pages: list[LayoutPage]
    removed_block_count: int
    removed_patterns: list[str]


def _normalize_block_text(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _matches_drm_pattern(text: str, config: WatermarkFilterConfig) -> bool:
    if DRM_EMAIL_ORDER_RE.search(text) or DRM_NAME_EMAIL_RE.match(text.strip()):
        return True
    return any(pattern.search(text) for pattern in config.extra_patterns)


def _in_header_footer(
    block: LayoutBlock, page: LayoutPage, config: WatermarkFilterConfig
) -> bool:
    header_limit = page.height * config.header_margin_ratio
    footer_limit = page.height * (1.0 - config.footer_margin_ratio)
    return block.bbox.y1 < header_limit or block.bbox.y0 > footer_limit


def _text_page_map(pages: list[LayoutPage]) -> dict[str, set[int]]:
    mapping: dict[str, set[int]] = {}
    for page in pages:
        seen_on_page: set[str] = set()
        for block in page.blocks:
            normalized = _normalize_block_text(block.text)
            if not normalized or len(normalized) > 200:
                continue
            if normalized in seen_on_page:
                continue
            seen_on_page.add(normalized)
            mapping.setdefault(normalized, set()).add(page.page_number)
    return mapping


def _is_decorative_title_block(
    block: LayoutBlock,
    page: LayoutPage,
    block_idx: int,
) -> bool:
    median = page_median_font(page.blocks)
    if is_decorative_spread_title(block, page, median_font=median):
        return True
    if block_idx > 0 and is_spread_title_pair(
        page.blocks[block_idx - 1],
        block,
        page,
        median_font=median,
    ):
        return True
    return False


def _is_layout_noise_block(
    block: LayoutBlock,
    page: LayoutPage,
    block_idx: int,
    *,
    config: WatermarkFilterConfig,
) -> bool:
    if is_page_number_label_block(block):
        return True
    if is_vertical_running_header(block, page):
        return True
    return _is_decorative_title_block(block, page, block_idx)


def _should_remove_block(
    block: LayoutBlock,
    page: LayoutPage,
    *,
    normalized: str,
    distinct_page_count: int,
    total_pages: int,
    config: WatermarkFilterConfig,
) -> bool:
    if not normalized:
        return False

    has_drm = _matches_drm_pattern(block.text, config)
    if has_drm:
        return True

    min_pages = max(config.min_page_count, int(total_pages * config.min_page_ratio))
    is_repeated = distinct_page_count >= min_pages
    if not is_repeated:
        return False

    if len(normalized) > config.max_block_length:
        return False

    in_band = _in_header_footer(block, page, config)
    has_email = bool(EMAIL_RE.search(block.text))

    return has_email or in_band


def filter_watermark_blocks(
    pages: list[LayoutPage],
    *,
    config: WatermarkFilterConfig | None = None,
) -> WatermarkFilterResult:
    """Remove DRM/personalization watermark blocks from extracted layout pages."""
    if not pages:
        return WatermarkFilterResult(pages=[], removed_block_count=0, removed_patterns=[])

    cfg = config or WatermarkFilterConfig()
    text_pages = _text_page_map(pages)
    total_pages = len(pages)
    removed_patterns: list[str] = []
    removed_block_count = 0
    filtered_pages: list[LayoutPage] = []

    for page in pages:
        kept_blocks: list[LayoutBlock] = []
        for block_idx, block in enumerate(page.blocks):
            normalized = _normalize_block_text(block.text)
            distinct_page_count = len(text_pages.get(normalized, set()))
            if _is_layout_noise_block(block, page, block_idx, config=cfg):
                removed_block_count += 1
                if (
                    normalized
                    and normalized not in removed_patterns
                    and len(removed_patterns) < cfg.max_removed_patterns
                ):
                    removed_patterns.append(normalized)
                continue
            if _should_remove_block(
                block,
                page,
                normalized=normalized,
                distinct_page_count=distinct_page_count,
                total_pages=total_pages,
                config=cfg,
            ):
                removed_block_count += 1
                if (
                    normalized
                    and normalized not in removed_patterns
                    and len(removed_patterns) < cfg.max_removed_patterns
                ):
                    removed_patterns.append(normalized)
                continue
            kept_blocks.append(block)
        filtered_pages.append(rebuild_layout_page(page, kept_blocks))

    return WatermarkFilterResult(
        pages=filtered_pages,
        removed_block_count=removed_block_count,
        removed_patterns=removed_patterns,
    )
