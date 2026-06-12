from rpg_assistant.ingestion.raw.filtering import filter_watermark_blocks
from rpg_assistant.ingestion.raw.layout import LayoutPage
from tests.fixtures.layout import make_block as _make_block

WATERMARK = (
    "Edouard WILLISSECK - edouard.willisseck@gmail.com - 202606/1783361/3032841"
)
BODY = "Elsirianne Horsbi est une erudite de Piemont."


def _block(page_number: int, block_index: int, text: str, *, y0: float = 100.0, y1: float = 120.0):
    return _make_block(
        page_number,
        block_index,
        text,
        font_size=None,
        x0=10.0,
        y0=y0,
        x1=400.0,
        y1=y1,
    )


def _page(page_number: int, blocks, *, height: float = 800.0) -> LayoutPage:
    from tests.fixtures.layout import make_page

    return make_page(blocks, page_number=page_number, width=600.0, height=height)


def _document_with_repeated_watermark(page_count: int, watermark_pages: int) -> list[LayoutPage]:
    pages: list[LayoutPage] = []
    for page_number in range(1, page_count + 1):
        blocks = [_block(page_number, 0, BODY)]
        if page_number <= watermark_pages:
            blocks.append(_block(page_number, 1, WATERMARK, y0=20.0, y1=35.0))
        pages.append(_page(page_number, blocks))
    return pages


def test_repeated_watermark_removed_on_most_pages():
    pages = _document_with_repeated_watermark(20, 15)
    result = filter_watermark_blocks(pages)

    assert result.removed_block_count == 15
    assert WATERMARK.lower() in " ".join(result.removed_patterns)
    for page in result.pages:
        texts = [block.text for block in page.blocks]
        assert WATERMARK not in texts
        assert BODY in texts


def test_unique_body_text_preserved():
    pages = [_page(1, [_block(1, 0, BODY)])]
    result = filter_watermark_blocks(pages)

    assert result.removed_block_count == 0
    assert result.pages[0].blocks[0].text == BODY


def test_page_number_labels_removed():
    pages = [
        _page(page_number, [_block(page_number, 0, f"PAGE {page_number}")])
        for page_number in range(1, 21)
    ]
    result = filter_watermark_blocks(pages)

    assert result.removed_block_count == 20
    assert len(result.pages) == 20
    assert all(page.blocks == [] for page in result.pages)


def test_single_page_drm_watermark_removed_by_regex():
    pages = [_page(1, [_block(1, 0, BODY), _block(1, 1, WATERMARK)])]
    result = filter_watermark_blocks(pages)

    assert result.removed_block_count == 1
    assert len(result.pages[0].blocks) == 1
    assert result.pages[0].blocks[0].text == BODY


def test_surviving_blocks_are_reindexed_and_page_text_rebuilt():
    pages = [_page(1, [_block(1, 0, BODY), _block(1, 1, WATERMARK)])]
    result = filter_watermark_blocks(pages)

    page = result.pages[0]
    assert page.text == BODY
    assert len(page.blocks) == 1
    assert page.blocks[0].block_index == 0
