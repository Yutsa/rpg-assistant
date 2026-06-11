"""COF2 Le Dernier Faelys: page 20 CONCLUSION(S) subsections."""

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


def _faelys_conclusion_pages() -> list[LayoutPage]:
    blocks = [
        _block(
            20,
            0,
            "CONCLUSION(S)",
            x0=42,
            y0=55,
            x1=200,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            20,
            1,
            "L'aventure est volontairement ouverte.",
            x0=42,
            y0=80,
            x1=227,
            y1=100,
        ),
        _block(
            20,
            2,
            "Le combat contre l'hydre",
            x0=42,
            y0=120,
            x1=200,
            y1=135,
            font_size=11,
            bold=True,
        ),
        _block(
            20,
            3,
            "C'est un adversaire redoutable. L'aide des centaures est préférable.",
            x0=42,
            y0=140,
            x1=227,
            y1=180,
        ),
        _block(
            20,
            4,
            "La révélation\ndu rôle d'Épitialm",
            x0=42,
            y0=200,
            x1=200,
            y1=225,
            font_size=11,
            bold=True,
        ),
        _block(
            20,
            5,
            "Une sorte de conseil peut se tenir pour révéler la duplicité de la reine.",
            x0=42,
            y0=230,
            x1=227,
            y1=270,
        ),
        _block(
            20,
            6,
            "La fermeture du portail",
            x0=248,
            y0=120,
            x1=400,
            y1=135,
            font_size=11,
            bold=True,
        ),
        _block(
            20,
            7,
            "Si Lymène Harpe d'Or quitte le val, le portail se ferme.",
            x0=248,
            y0=140,
            x1=424,
            y1=200,
        ),
        _block(
            20,
            8,
            "L'échec",
            x0=248,
            y0=220,
            x1=300,
            y1=235,
            font_size=11,
            bold=True,
        ),
        _block(
            20,
            9,
            "Si le serpent tueur mord Manthine, le venin agit lentement.",
            x0=248,
            y0=240,
            x1=424,
            y1=300,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=20, width=510, height=650, text="", blocks=[]),
            blocks,
        )
    ]


def test_faelys_conclusion_section_hierarchy():
    pages = _faelys_conclusion_pages()
    result = detect_sections(pages, campaign_id="dernier-faelys", document_id="doc_end")
    by_title = {section.title: section for section in result.sections}

    conclusion = by_title["CONCLUSION(S)"]
    assert conclusion.level == 1

    for title in (
        "Le combat contre l'hydre",
        "La révélation\ndu rôle d'Épitialm",
        "La fermeture du portail",
        "L'échec",
    ):
        section = by_title[title]
        assert section.level == 2
        assert section.parent_section_id == conclusion.id


def test_faelys_conclusion_chunks_are_separate():
    pages = _faelys_conclusion_pages()
    section_result = detect_sections(
        pages, campaign_id="dernier-faelys", document_id="doc_end"
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="dernier-faelys",
        document_id="doc_end",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )
    sec_by_title = {s.title: s.id for s in section_result.sections}

    hydra = next(
        c for c in chunks if c.section_id == sec_by_title["Le combat contre l'hydre"]
    )
    revelation = next(
        c
        for c in chunks
        if c.section_id == sec_by_title["La révélation\ndu rôle d'Épitialm"]
    )

    assert "adversaire redoutable" in hydra.text
    assert "duplicité de la reine" not in hydra.text
    assert "duplicité de la reine" in revelation.text
