"""Tests for COF2-style intro pages (sidebar boxes, illustration gap, title case)."""

from rpg_assistant.ingestion.raw.chunking import build_chunks
from rpg_assistant.ingestion.raw.filtering import filter_watermark_blocks
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


def _mondanites_intro_pages() -> list[LayoutPage]:
    page_five_blocks = [
        _block(5, 0, "FICHE TECHNIQUE", x0=291, y0=225, x1=388, y1=238, font_size=11.5, bold=True),
        _block(
            5,
            1,
            "Type • Action/Enquête\nPJ • Niveau 5/6",
            x0=262,
            y0=243,
            x1=361,
            y1=330,
            font_size=9,
            bold=True,
        ),
        _block(
            5,
            2,
            "Si beaucoup ont oublié les chroniques des\nTerres d'Osgild, certains essaient de décou-",
            x0=42,
            y0=382,
            x1=227,
            y1=445,
            font_size=18,
            bold=True,
        ),
        _block(
            5,
            3,
            "PARTIE I :\nL'HISTOIRE EN UN COUP D'ŒIL",
            x0=43,
            y0=459,
            x1=225,
            y1=489,
            font_size=14,
            bold=True,
        ),
        _block(
            5,
            4,
            "Vous trouverez dans cette partie les informa-\ntions expliquant le contexte et les secrets du\nscénario.",
            x0=43,
            y0=493,
            x1=227,
            y1=551,
            font_size=9.5,
        ),
        _block(
            5, 5, "Les grandes lignes", x0=248, y0=389, x1=368, y1=404, font_size=13, bold=True
        ),
        _block(
            5,
            6,
            "Les PJ sont invités à une soirée mondaine orga-\nnisée dans le cabinet de curiosités d'Elsirianne.",
            x0=248,
            y0=406,
            x1=433,
            y1=567,
            font_size=9.5,
        ),
        _block(
            5, 7, "EN QUELQUES MOTS", x0=78, y0=219, x1=190, y1=232, font_size=11.5, bold=True
        ),
        _block(
            5,
            8,
            "Pendant une soirée de présentation de la col-\nlection privée d'une érudite de Piémont, la\nmomie s'éveille.",
            x0=48,
            y0=237,
            x1=222,
            y1=356,
            font_size=9,
        ),
    ]
    page_six = LayoutPage(page_number=6, width=510, height=650, text="", blocks=[])
    page_seven_blocks = [
        _block(
            7,
            0,
            "Dans les vestiges d'un temple dissimulé sous les\nabattoirs, les PJ découvrent un plan terrifiant",
            x0=43,
            y0=46,
            x1=227,
            y1=115,
            font_size=9.5,
        ),
        _block(
            7, 1, "L'histoire pour le MJ", x0=43, y0=123, x1=177, y1=138, font_size=13, bold=True
        ),
        _block(
            7,
            2,
            "Taless Rhann était l'un des plus sanglants généraux elfes du Roi-Sorcier.",
            x0=43,
            y0=140,
            x1=227,
            y1=357,
            font_size=9.5,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=5, width=510, height=650, text="", blocks=[]),
            page_five_blocks,
        ),
        page_six,
        rebuild_layout_page(
            LayoutPage(page_number=7, width=510, height=650, text="", blocks=[]),
            page_seven_blocks,
        ),
    ]


def test_intro_layout_sections_have_no_false_parents():
    pages = _mondanites_intro_pages()
    result = detect_sections(pages, campaign_id="momie", document_id="doc_intro")

    titles = [section.title for section in result.sections]
    assert "EN QUELQUES MOTS" in titles
    assert "FICHE TECHNIQUE" in titles
    assert "Les grandes lignes" in titles
    assert not any(title == "ET MOMIE" for title in titles)
    assert not any(title == "MONDANITÉS" for title in titles)

    by_title = {section.title: section for section in result.sections}
    assert by_title["EN QUELQUES MOTS"].parent_section_id is None
    assert by_title["FICHE TECHNIQUE"].parent_section_id is None
    assert by_title["Les grandes lignes"].parent_section_id is None
    partie = next(s for s in result.sections if s.title.startswith("PARTIE I"))
    assert partie.parent_section_id is None
    assert by_title["EN QUELQUES MOTS"].parent_section_id != partie.id


def test_intro_layout_chunks_partition_sidebar_and_continuation():
    pages = _mondanites_intro_pages()
    section_result = detect_sections(pages, campaign_id="momie", document_id="doc_intro")
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="momie",
        document_id="doc_intro",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )
    sec_by_title = {s.title: s.id for s in section_result.sections}
    by_section = {}
    for chunk in chunks:
        by_section.setdefault(chunk.section_id, []).append(chunk)

    en_quelques = by_section[sec_by_title["EN QUELQUES MOTS"]]
    assert len(en_quelques) == 1
    assert "momie s'éveille" in en_quelques[0].text
    assert "vestiges d'un temple" not in en_quelques[0].text

    fiche = by_section[sec_by_title["FICHE TECHNIQUE"]]
    assert len(fiche) == 1
    assert "Action/Enquête" in fiche[0].text
    assert "Terres d'Osgild" not in fiche[0].text

    intro = by_section[sec_by_title["Introduction"]]
    assert len(intro) == 1
    assert "Terres d'Osgild" in intro[0].text

    grandes_lignes = by_section[sec_by_title["Les grandes lignes"]]
    assert len(grandes_lignes) == 1
    assert "cabinet de curiosités" in grandes_lignes[0].text
    assert "vestiges d'un temple" in grandes_lignes[0].text
    assert grandes_lignes[0].page_end == 7

    partie_id = next(s.id for s in section_result.sections if s.title.startswith("PARTIE I"))
    partie_chunks = by_section[partie_id]
    assert len(partie_chunks) == 1
    assert "contexte et les secrets" in partie_chunks[0].text
    assert "vestiges d'un temple" not in partie_chunks[0].text


def test_filter_removes_page_footer_in_margin():
    pages = [
        LayoutPage(
            page_number=5,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(5, 0, "Body text.", x0=40, y0=200, x1=200, y1=220),
                _block(5, 1, "PAGE 3", x0=332, y0=605, x1=374, y1=616, font_size=9, bold=True),
            ],
        )
    ]
    result = filter_watermark_blocks(pages)
    assert len(result.pages[0].blocks) == 1
    assert result.pages[0].blocks[0].text == "Body text."
