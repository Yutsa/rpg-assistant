"""Unit tests for Docling → internal element conversion."""

from __future__ import annotations

from rpg_core.models.raw import BBox
from rpg_ingest.raw.docling_convert import elements_to_layout_pages
from rpg_ingest.raw.elements import DocElement
from rpg_ingest.raw.docling_sections import detect_sections_from_elements


def _element(
    index: int,
    element_type: str,
    text: str,
    *,
    page: int = 1,
    block_index: int | None = None,
    heading_level: int | None = None,
) -> DocElement:
    return DocElement(
        element_index=index,
        element_type=element_type,
        text=text,
        page_number=page,
        block_index=block_index if block_index is not None else index,
        bbox=BBox(x0=0, y0=index * 30, x1=200, y1=index * 30 + 20),
        heading_level=heading_level,
    )


def test_elements_to_layout_pages_preserves_blocks():
    elements = [
        _element(0, "heading", "Chapter 1", heading_level=1),
        _element(1, "paragraph", "Body text."),
    ]
    pages = elements_to_layout_pages(
        elements,
        page_sizes={1: (612.0, 792.0)},
    )
    assert len(pages) == 1
    assert len(pages[0].blocks) == 2
    assert pages[0].blocks[0].text == "Chapter 1"
    assert pages[0].blocks[1].text == "Body text."


def test_detect_sections_from_elements_builds_hierarchy():
    elements = [
        _element(0, "title", "Adventure", heading_level=1),
        _element(1, "paragraph", "Intro."),
        _element(2, "heading", "Scene One", heading_level=2),
        _element(3, "paragraph", "Scene body."),
        _element(4, "heading", "Scene Two", heading_level=2),
        _element(5, "list_item", "- Item A"),
    ]
    pages = elements_to_layout_pages(elements, page_sizes={1: (612.0, 792.0)})
    result = detect_sections_from_elements(
        elements,
        pages,
        campaign_id="camp",
        document_id="doc_test",
    )
    assert len(result.sections) == 3
    assert result.sections[0].title == "Adventure"
    assert result.sections[0].level == 1
    assert result.sections[1].title == "Scene One"
    assert result.sections[1].level == 2
    assert result.sections[1].parent_section_id == result.sections[0].id
    assert result.sections[2].title == "Scene Two"
    assert result.heading_anchors == [(1, 0), (1, 2), (1, 4)]


def test_detect_sections_fallback_without_headings():
    elements = [_element(0, "paragraph", "Only body.")]
    pages = elements_to_layout_pages(elements, page_sizes={1: (612.0, 792.0)})
    result = detect_sections_from_elements(
        elements,
        pages,
        campaign_id="camp",
        document_id="doc_test",
    )
    assert len(result.sections) == 1
    assert result.sections[0].title == "Document"
    assert result.heading_anchors == []
