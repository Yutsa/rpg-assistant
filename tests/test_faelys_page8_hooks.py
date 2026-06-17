"""COF2 Le Dernier Faelys: page 8 IMPLICATION DES PJ hooks."""

from rpg_ingest.raw.chunking import build_chunks
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_ingest.raw.sections import detect_sections, refine_section_page_ends
from rpg_core.models.raw import BBox


def _block(
    page: int,
    index: int,
    text: str,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    font_size: float = 9.5,
    bold: bool = False,
) -> LayoutBlock:
    return LayoutBlock(
        page_number=page,
        block_index=index,
        text=text,
        bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
        metadata={
            "max_font_size": font_size,
            "avg_font_size": font_size,
            "is_bold": bold,
        },
    )


def _faelys_page8_pages() -> list[LayoutPage]:
    blocks = [
        _block(
            8,
            0,
            "IMPLICATION DES PJ",
            x0=42,
            y0=55,
            x1=227,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            8,
            1,
            "Choisissez l'introduction la plus adaptée à votre groupe.",
            x0=42,
            y0=80,
            x1=227,
            y1=110,
        ),
        _block(
            8,
            2,
            "Si vous avez joué Les\nEntraves du destin",
            x0=42,
            y0=130,
            x1=227,
            y1=155,
            font_size=11,
            bold=True,
        ),
        _block(
            8,
            3,
            "Les PJ restent au château et reçoivent le message de Bran le Fol.",
            x0=42,
            y0=160,
            x1=227,
            y1=210,
        ),
        _block(
            8,
            4,
            "Si vos PJ sont nobles",
            x0=42,
            y0=230,
            x1=180,
            y1=245,
            font_size=11,
            bold=True,
        ),
        _block(
            8,
            5,
            "Ils peuvent être présents au château au moment de l'arrivée du satyre.",
            x0=42,
            y0=250,
            x1=227,
            y1=300,
        ),
        _block(
            8,
            6,
            "Si vos PJ ne sont pas au\nchâteau",
            x0=42,
            y0=320,
            x1=227,
            y1=345,
            font_size=11,
            bold=True,
        ),
        _block(
            8,
            7,
            "Les PJ assistent à l'arrivée en ville du satyre enchaîné.",
            x0=42,
            y0=350,
            x1=227,
            y1=400,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=8, width=510, height=650, text="", blocks=[]),
            blocks,
        ),
        LayoutPage(page_number=9, width=510, height=650, text="", blocks=[]),
    ]


def test_faelys_page8_hook_hierarchy():
    pages = _faelys_page8_pages()
    result = detect_sections(pages, campaign_id="dernier-faelys", document_id="doc_p8")
    by_title = {section.title: section for section in result.sections}

    implication = by_title["IMPLICATION DES PJ"]
    assert implication.level == 1

    for hook_title in (
        "Si vous avez joué Les\nEntraves du destin",
        "Si vos PJ sont nobles",
        "Si vos PJ ne sont pas au\nchâteau",
    ):
        hook = by_title[hook_title]
        assert hook.level == 2
        assert hook.parent_section_id == implication.id
        assert hook.level != 1


def test_faelys_page8_hook_page_end_and_chunks():
    pages = _faelys_page8_pages()
    section_result = detect_sections(
        pages, campaign_id="dernier-faelys", document_id="doc_p8"
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="dernier-faelys",
        document_id="doc_p8",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )
    refine_section_page_ends(section_result.sections, chunks)

    chateau = next(
        s for s in section_result.sections if "ne sont pas au" in s.title
    )
    assert chateau.page_end == 8

    sec_by_title = {s.title: s.id for s in section_result.sections}
    hook_chunk = next(
        c
        for c in chunks
        if c.section_id == sec_by_title["Si vos PJ ne sont pas au\nchâteau"]
    )
    assert "satyre enchaîné" in hook_chunk.text
