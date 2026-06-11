from rpg_assistant.ingestion.raw.layout import LayoutBlock
from rpg_assistant.models.raw import BBox


def test_layout_block_stores_bbox_and_metadata():
    block = LayoutBlock(
        page_number=3,
        block_index=2,
        text="Sample block",
        bbox=BBox(x0=10, y0=20, x1=100, y1=40),
        metadata={"max_font_size": 14.0, "is_bold": True},
    )
    assert block.page_number == 3
    assert block.bbox.x1 == 100
    assert block.metadata["is_bold"] is True
