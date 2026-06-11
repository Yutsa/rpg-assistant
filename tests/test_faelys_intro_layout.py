"""COF2 Le Dernier Faelys: intro page 6 banner + L'histoire bi-column wrap."""

from rpg_assistant.ingestion.raw.block_merging import merge_fragmented_blocks
from rpg_assistant.ingestion.raw.chunking import build_chunks
from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.models.raw import BBox


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


def _faelys_intro_pages() -> list[LayoutPage]:
    page_six_blocks = [
        _block(
            6,
            0,
            "INTRODUCTION POUR LE MJ",
            x0=42,
            y0=55,
            x1=227,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            6,
            1,
            "L'histoire",
            x0=42,
            y0=91,
            x1=120,
            y1=108,
            font_size=13,
            bold=True,
        ),
        _block(
            6,
            2,
            "Le val de l'Orm est une région du plan de\nl'ombre féérique qui connait une période trouble.",
            x0=42,
            y0=112,
            x1=227,
            y1=200,
        ),
        _block(
            6,
            3,
            "L'arrivée de ces humains fit débat. Épitialm considéra\nque cela affaiblissait le val.",
            x0=42,
            y0=205,
            x1=227,
            y1=287,
        ),
        _block(
            6,
            4,
            "Ekhidna, la mère des monstres, envoya ses enfants.\nOrthos, le lion, fut tué. Thalamie fut enlevée.",
            x0=248,
            y0=91,
            x1=424,
            y1=280,
        ),
        _block(
            6,
            5,
            "Au",
            x0=248,
            y0=285,
            x1=260,
            y1=295,
        ),
    ]
    page_seven_blocks = [
        _block(
            7,
            0,
            "cours de cette surveillance que l'aigle poursuit\nun serpent jusqu'au plan matériel.",
            x0=42,
            y0=45,
            x1=227,
            y1=103,
        ),
        _block(
            7,
            1,
            "Le portail",
            x0=42,
            y0=120,
            x1=120,
            y1=135,
            font_size=13,
            bold=True,
        ),
        _block(
            7,
            2,
            "La comtesse de Sénice découvrit une arche de pierre.",
            x0=42,
            y0=140,
            x1=227,
            y1=220,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=6, width=510, height=650, text="", blocks=[]),
            page_six_blocks,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=7, width=510, height=650, text="", blocks=[]),
            page_seven_blocks,
        ),
    ]


def _pipeline_pages():
    pages = _faelys_intro_pages()
    return merge_fragmented_blocks(pages).pages


def test_faelys_intro_sections_banner_parents_histoire():
    pages = _pipeline_pages()
    result = detect_sections(pages, campaign_id="dernier-faelys", document_id="doc_faelys")

    by_title = {section.title: section for section in result.sections}
    assert "INTRODUCTION POUR LE MJ" in by_title
    assert "L'histoire" in by_title
    intro = by_title["INTRODUCTION POUR LE MJ"]
    histoire = by_title["L'histoire"]
    assert intro.level == 1
    assert histoire.level == 2
    assert histoire.parent_section_id == intro.id


def test_faelys_intro_chunks_assign_right_column_to_histoire():
    pages = _pipeline_pages()
    section_result = detect_sections(
        pages, campaign_id="dernier-faelys", document_id="doc_faelys"
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="dernier-faelys",
        document_id="doc_faelys",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )
    sec_by_title = {s.title: s.id for s in section_result.sections}
    intro_chunks = [c for c in chunks if c.section_id == sec_by_title["INTRODUCTION POUR LE MJ"]]
    histoire_chunks = [c for c in chunks if c.section_id == sec_by_title["L'histoire"]]

    assert not intro_chunks or all("Ekhidna" not in c.text for c in intro_chunks)
    assert histoire_chunks
    histoire_text = " ".join(c.text for c in histoire_chunks)
    assert "val de l'Orm" in histoire_text
    assert "Ekhidna" in histoire_text
    assert "Orthos" in histoire_text
    assert "Thalamie" in histoire_text
    assert "Au cours de cette surveillance" in histoire_text
    assert "Le portail" not in histoire_text or "arche de pierre" not in histoire_text
