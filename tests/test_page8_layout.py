"""Synthetic page-8 bi-column layout: MJ story continuation, actors, PARTIE II."""

from rpg_ingest.raw.chunking import build_chunks
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_ingest.raw.sections import detect_sections
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


def _page8_fixture_pages() -> list[LayoutPage]:
    page_seven_blocks = [
        _block(
            7,
            0,
            "PARTIE I :\nL'HISTOIRE EN UN COUP D'ŒIL",
            x0=43,
            y0=46,
            x1=225,
            y1=76,
            font_size=14,
            bold=True,
        ),
        _block(
            7,
            1,
            "L'histoire pour le MJ",
            x0=43,
            y0=123,
            x1=177,
            y1=138,
            font_size=13,
            bold=True,
        ),
        _block(
            7,
            2,
            "Taless Rhann était l'un des plus sanglants généraux elfes.",
            x0=43,
            y0=140,
            x1=227,
            y1=250,
        ),
        _block(
            7,
            3,
            "La tombe resta inviolée pendant plusieurs millénaires.",
            x0=43,
            y0=358,
            x1=227,
            y1=450,
        ),
    ]
    page_eight_blocks = [
        _block(
            8,
            0,
            "Il est temps pour les PJ de découvrir la vérité sur la momie.",
            x0=43,
            y0=46,
            x1=227,
            y1=90,
        ),
        _block(
            8,
            1,
            "Les héros doivent agir vite avant que tout ne bascule.",
            x0=43,
            y0=95,
            x1=227,
            y1=130,
        ),
        _block(
            8,
            2,
            "Les différents acteurs",
            x0=43,
            y0=250,
            x1=200,
            y1=265,
            font_size=13,
            bold=True,
        ),
        _block(
            8,
            3,
            "• Kalian : marchand ambitieux et rusé.",
            x0=43,
            y0=270,
            x1=227,
            y1=300,
        ),
        _block(
            8,
            4,
            "• Hector : garde du corps loyal.",
            x0=248,
            y0=46,
            x1=433,
            y1=76,
        ),
        _block(
            8,
            5,
            "• Elsirianne : érudite de Piémont.",
            x0=248,
            y0=80,
            x1=433,
            y1=110,
        ),
        _block(
            8,
            6,
            "PARTIE II :\nL'ENQUÊTE",
            x0=248,
            y0=459,
            x1=400,
            y1=489,
            font_size=14,
            bold=True,
        ),
        _block(
            8,
            7,
            "Corps de la partie II.",
            x0=248,
            y0=493,
            x1=433,
            y1=551,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=7, width=510, height=650, text="", blocks=[]),
            page_seven_blocks,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=8, width=510, height=650, text="", blocks=[]),
            page_eight_blocks,
        ),
    ]


def test_page8_no_false_introduction_section():
    pages = _page8_fixture_pages()
    result = detect_sections(pages, campaign_id="momie", document_id="doc_page8")
    titles = [section.title for section in result.sections]
    assert "Introduction" not in titles


def test_page8_chunks_assign_mj_story_and_actors():
    pages = _page8_fixture_pages()
    section_result = detect_sections(pages, campaign_id="momie", document_id="doc_page8")
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="momie",
        document_id="doc_page8",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )
    sec_by_title = {s.title: s.id for s in section_result.sections}
    by_section: dict[str | None, list] = {}
    for chunk in chunks:
        by_section.setdefault(chunk.section_id, []).append(chunk)

    histoire_mj = next(
        s for s in section_result.sections if s.title == "L'histoire pour le MJ"
    )
    acteurs = next(
        s for s in section_result.sections if s.title == "Les différents acteurs"
    )
    mj_chunks = by_section.get(histoire_mj.id, [])
    assert mj_chunks
    mj_text = " ".join(c.text for c in mj_chunks)
    assert "Il est temps pour les PJ" in mj_text
    assert "Kalian" not in mj_text

    acteurs_chunks = by_section.get(acteurs.id, [])
    assert acteurs_chunks
    acteurs_text = " ".join(c.text for c in acteurs_chunks)
    assert "Kalian" in acteurs_text
    assert "Hector" in acteurs_text
    assert "Il est temps pour les PJ" not in acteurs_text

    intro_ids = {
        s.id for s in section_result.sections if s.title == "Introduction"
    }
    for intro_id in intro_ids:
        page8_intro = [
            c
            for c in by_section.get(intro_id, [])
            if c.page_start <= 8 <= c.page_end
        ]
        assert not page8_intro
