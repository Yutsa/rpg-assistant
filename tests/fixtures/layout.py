from __future__ import annotations

from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_core.models.raw import BBox


def make_block(
    page_number: int,
    block_index: int,
    text: str,
    *,
    font_size: float | None = None,
    bold: bool = False,
    italic: bool = False,
    x0: float = 0.0,
    y0: float = 0.0,
    x1: float = 100.0,
    y1: float | None = None,
    metadata: dict | None = None,
) -> LayoutBlock:
    if y1 is None:
        y1 = y0 + 20.0
    block_metadata = dict(metadata or {})
    if font_size is not None:
        block_metadata.setdefault("max_font_size", font_size)
        block_metadata.setdefault("avg_font_size", font_size)
        block_metadata.setdefault("is_bold", bold)
        block_metadata.setdefault("is_italic", italic)
        block_metadata.setdefault("line_count", text.count("\n") + 1)
    return LayoutBlock(
        page_number=page_number,
        block_index=block_index,
        text=text,
        bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
        metadata=block_metadata,
    )


def make_page(
    blocks: list[LayoutBlock],
    *,
    page_number: int | None = None,
    width: float = 612.0,
    height: float = 792.0,
) -> LayoutPage:
    page_num = page_number if page_number is not None else blocks[0].page_number
    return LayoutPage(
        page_number=page_num,
        width=width,
        height=height,
        text="\n\n".join(block.text for block in blocks),
        blocks=blocks,
    )
