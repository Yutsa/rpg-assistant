from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.models.raw import BBox


def _block(page: int, index: int, text: str, font_size: float, bold: bool = False) -> LayoutBlock:
    return LayoutBlock(
        page_number=page,
        block_index=index,
        text=text,
        bbox=BBox(x0=0, y0=0, x1=100, y1=20),
        metadata={
            "max_font_size": font_size,
            "avg_font_size": font_size,
            "is_bold": bold,
        },
    )


def test_detect_sections_finds_chapter_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Chapter 1\nIntro body text here.",
            blocks=[
                _block(1, 0, "Chapter 1", 18, bold=True),
                _block(1, 1, "Intro body text here.", 11),
            ],
        ),
        LayoutPage(
            page_number=2,
            width=612,
            height=792,
            text="Chapter 2\nMore content.",
            blocks=[
                _block(2, 0, "Chapter 2", 18, bold=True),
                _block(2, 1, "More content.", 11),
            ],
        ),
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert len(result.sections) == 2
    assert result.sections[0].title == "Chapter 1"
    assert result.sections[0].level == 1
    assert result.sections[1].title == "Chapter 2"
    assert result.heading_anchors == [(1, 0), (2, 0)]


def test_detect_sections_fallback_when_no_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Plain paragraph without headings.",
            blocks=[_block(1, 0, "Plain paragraph without headings.", 11)],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert len(result.sections) == 1
    assert result.sections[0].title == "Document"
    assert result.heading_anchors == []


def test_detect_sections_rejects_single_character_drop_cap_heading():
    pages = [
        LayoutPage(
            page_number=5,
            width=612,
            height=792,
            text="S\ni beaucoup ont oublié.",
            blocks=[
                _block(5, 0, "S", 24, bold=True),
                _block(5, 1, "i beaucoup ont oublié.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    titles = [section.title for section in result.sections]
    assert "S" not in titles


def test_detect_sections_keeps_three_character_bold_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Fin\nNotes here.",
            blocks=[
                _block(1, 0, "Fin", 16, bold=True),
                _block(1, 1, "Notes here.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert [section.title for section in result.sections] == ["Fin"]


def test_detect_sections_rejects_two_character_bold_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="GM\nNotes here.",
            blocks=[
                _block(1, 0, "GM", 16, bold=True),
                _block(1, 1, "Notes here.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert result.sections[0].title == "Document"
