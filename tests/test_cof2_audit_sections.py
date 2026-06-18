"""COF2 audit regressions — sections (issues 3 & 4)."""

from __future__ import annotations

from rpg_ingest.raw.block_merging import merge_fragmented_blocks
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_ingest.raw.sections import detect_sections
from rpg_ingest.raw.stat_blocks import resolve_profile
from rpg_core.models.raw import BBox
from tests.fixtures.cof2_audit_expectations import (
    FAELYS_IMPLICATION_SECTION,
    FAELYS_SHADOW_BOX_TITLE,
    FAELYS_SHADOW_BOX_TRUNCATED,
    FAELYS_ZONE_TITLES,
)
from tests.fixtures.pipeline import run_raw_extraction_pipeline, section_by_title


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


def _faelys_shadow_plan_pages_single_block() -> list[LayoutPage]:
    blocks = [
        _block(
            7,
            0,
            f"{FAELYS_SHADOW_BOX_TRUNCATED}\nL'OMBRE FEERIQUE",
            x0=42,
            y0=120,
            x1=227,
            y1=160,
            font_size=12,
            bold=True,
        ),
        _block(
            7,
            1,
            "Les félis complotent pour renverser la reine Épitialm.",
            x0=42,
            y0=170,
            x1=227,
            y1=280,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=7, width=510, height=650, text="", blocks=[]),
            blocks,
        )
    ]


def _faelys_shadow_plan_pages_split_blocks() -> list[LayoutPage]:
    blocks = [
        _block(
            7,
            0,
            FAELYS_SHADOW_BOX_TRUNCATED,
            x0=42,
            y0=120,
            x1=227,
            y1=140,
            font_size=12,
            bold=True,
        ),
        _block(
            7,
            1,
            "L'OMBRE FEERIQUE",
            x0=42,
            y0=142,
            x1=227,
            y1=160,
            font_size=12,
            bold=True,
        ),
        _block(
            7,
            2,
            "Les félis complotent pour renverser la reine Épitialm.",
            x0=42,
            y0=170,
            x1=227,
            y1=280,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=7, width=510, height=650, text="", blocks=[]),
            blocks,
        )
    ]


def _faelys_implication_then_zones_pages() -> list[LayoutPage]:
    page_eight = [
        _block(
            8,
            0,
            FAELYS_IMPLICATION_SECTION,
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
            3,
            "Ils peuvent être présents au château.",
            x0=42,
            y0=250,
            x1=227,
            y1=300,
        ),
    ]
    page_nine = [
        _block(
            9,
            0,
            "Les PJ quittent le château et se dirigent vers le val.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
    ]
    page_twelve = [
        _block(
            12,
            0,
            FAELYS_ZONE_TITLES[0],
            x0=42,
            y0=55,
            x1=200,
            y1=72,
            font_size=13,
            bold=True,
        ),
        _block(
            12,
            1,
            "La prairie est couverte de fleurs géantes et de sentiers sinueux.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
    ]
    page_nineteen = [
        _block(
            19,
            0,
            FAELYS_ZONE_TITLES[1],
            x0=42,
            y0=55,
            x1=200,
            y1=72,
            font_size=13,
            bold=True,
        ),
        _block(
            19,
            1,
            "La grotte abrite Ekhidna et ses enfants monstrueux.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=8, width=510, height=650, text="", blocks=[]),
            page_eight,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=9, width=510, height=650, text="", blocks=[]),
            page_nine,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=12, width=510, height=650, text="", blocks=[]),
            page_twelve,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=19, width=510, height=650, text="", blocks=[]),
            page_nineteen,
        ),
    ]


def test_faelys_shadow_box_title_not_truncated_single_block():
    """Audit issue 3 — multi-line encadré in one block must normalize to full title."""
    pages = _faelys_shadow_plan_pages_single_block()
    result = detect_sections(pages, campaign_id="dernier-faelys", document_id="doc_p7a")
    titles = [section.title for section in result.sections]
    normalized = [title.replace("\n", " ") for title in titles]

    assert FAELYS_SHADOW_BOX_TITLE in normalized
    assert any(section.title == FAELYS_SHADOW_BOX_TITLE for section in result.sections)
    assert FAELYS_SHADOW_BOX_TRUNCATED not in titles
    assert all(section.title != "Document" for section in result.sections)


def test_faelys_shadow_box_title_not_truncated_split_blocks():
    """Audit issue 3 — split encadré lines must merge to full title."""
    pages = _faelys_shadow_plan_pages_split_blocks()
    profile = resolve_profile("cof2", pages)
    merged = merge_fragmented_blocks(pages, profile=profile).pages

    heading_blocks = [
        block
        for block in merged[0].blocks
        if block.metadata.get("is_bold") and "FELIS" in block.text
    ]
    merged_heading_text = " ".join(block.text.replace("\n", " ") for block in heading_blocks)
    assert FAELYS_SHADOW_BOX_TITLE in merged_heading_text.replace("\n", " ")

    result = detect_sections(merged, campaign_id="dernier-faelys", document_id="doc_p7b")
    titles = [section.title for section in result.sections]
    assert FAELYS_SHADOW_BOX_TITLE in titles
    assert FAELYS_SHADOW_BOX_TRUNCATED not in titles


def test_faelys_zone_sections_not_children_of_implication():
    """Audit issue 4 — geographic zones must not parent under IMPLICATION DES PJ."""
    result = run_raw_extraction_pipeline(
        _faelys_implication_then_zones_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_faelys_hierarchy",
    )

    implication = section_by_title(result.sections, FAELYS_IMPLICATION_SECTION)
    assert implication.page_end <= 8, (
        f"IMPLICATION DES PJ page_end should stay on p.8, got {implication.page_end}"
    )

    for zone_title in FAELYS_ZONE_TITLES:
        zone = section_by_title(result.sections, zone_title)
        assert zone.parent_section_id != implication.id, (
            f"{zone_title!r} must not be a child of IMPLICATION DES PJ"
        )
        assert zone.parent_section_id is None, (
            f"{zone_title!r} should be a top-level section, got parent {zone.parent_section_id!r}"
        )
