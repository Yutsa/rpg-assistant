"""Convert DoclingDocument into internal elements and layout pages."""

from __future__ import annotations

from typing import Any

from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import (
    DocItem,
    GroupItem,
    ListItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
    TitleItem,
)
from docling_core.types.doc.labels import DocItemLabel

from rpg_core.models.raw import BBox
from rpg_ingest.raw.elements import (
    CONTENT_ELEMENT_TYPES,
    HEADING_ELEMENT_TYPES,
    SKIP_ELEMENT_TYPES,
    DocElement,
)
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page

_LABEL_TO_ELEMENT_TYPE: dict[DocItemLabel, str] = {
    DocItemLabel.TITLE: "title",
    DocItemLabel.SECTION_HEADER: "heading",
    DocItemLabel.PARAGRAPH: "paragraph",
    DocItemLabel.TEXT: "paragraph",
    DocItemLabel.LIST_ITEM: "list_item",
    DocItemLabel.TABLE: "table",
    DocItemLabel.PICTURE: "figure",
    DocItemLabel.CAPTION: "caption",
    DocItemLabel.CODE: "code",
    DocItemLabel.FORMULA: "formula",
    DocItemLabel.PAGE_HEADER: "page_header",
    DocItemLabel.PAGE_FOOTER: "page_footer",
    DocItemLabel.KEY_VALUE_REGION: "key_value",
    DocItemLabel.HANDWRITTEN_TEXT: "handwritten",
    DocItemLabel.MARKER: "marker",
    DocItemLabel.EMPTY_VALUE: "empty",
    DocItemLabel.FOOTNOTE: "paragraph",
    DocItemLabel.REFERENCE: "paragraph",
    DocItemLabel.FORM: "paragraph",
    DocItemLabel.FIELD_HEADING: "heading",
    DocItemLabel.FIELD_KEY: "key_value",
    DocItemLabel.FIELD_VALUE: "key_value",
    DocItemLabel.FIELD_HINT: "paragraph",
    DocItemLabel.DOCUMENT_INDEX: "paragraph",
    DocItemLabel.CHECKBOX_SELECTED: "list_item",
    DocItemLabel.CHECKBOX_UNSELECTED: "list_item",
}


def _page_heights(doc: DoclingDocument) -> dict[int, float]:
    heights: dict[int, float] = {}
    for page_no, page in doc.pages.items():
        heights[page_no] = float(page.size.height)
    return heights


def _bbox_to_top_left(
    bbox: Any,
    *,
    page_height: float,
) -> BBox:
    """Convert Docling BOTTOMLEFT bbox to top-left coordinates (PyMuPDF style)."""
    x0 = float(bbox.l)
    x1 = float(bbox.r)
    y0 = page_height - float(bbox.t)
    y1 = page_height - float(bbox.b)
    if y0 > y1:
        y0, y1 = y1, y0
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _item_text(item: DocItem, doc: DoclingDocument) -> str:
    if isinstance(item, TextItem):
        return (item.text or "").strip()
    if isinstance(item, TableItem):
        try:
            return item.export_to_markdown(doc).strip()
        except Exception:
            return (getattr(item, "text", None) or "").strip()
    if isinstance(item, GroupItem):
        parts: list[str] = []
        for child, _level in doc.iterate_items(root=item):
            if isinstance(child, DocItem) and not isinstance(child, GroupItem):
                part = _item_text(child, doc)
                if part:
                    parts.append(part)
        return "\n".join(parts).strip()
    return (getattr(item, "text", None) or "").strip()


def _element_type_for_item(item: DocItem) -> str:
    label = getattr(item, "label", None)
    if label is not None:
        mapped = _LABEL_TO_ELEMENT_TYPE.get(label)
        if mapped:
            return mapped
    if isinstance(item, TitleItem):
        return "title"
    if isinstance(item, SectionHeaderItem):
        return "heading"
    if isinstance(item, ListItem):
        return "list_item"
    if isinstance(item, TableItem):
        return "table"
    if isinstance(item, TextItem):
        return "paragraph"
    return "paragraph"


def _heading_level_for_item(item: DocItem, element_type: str) -> int | None:
    if element_type not in HEADING_ELEMENT_TYPES:
        return None
    if isinstance(item, SectionHeaderItem):
        return int(item.level)
    if isinstance(item, TitleItem):
        return 1
    return 1


def docling_document_to_elements(doc: DoclingDocument) -> list[DocElement]:
    """Map a DoclingDocument to ordered internal elements."""
    page_heights = _page_heights(doc)
    elements: list[DocElement] = []
    element_index = 0
    block_counters: dict[int, int] = {}

    for item, _stack_level in doc.iterate_items():
        if not isinstance(item, DocItem):
            continue
        if not item.prov:
            continue

        element_type = _element_type_for_item(item)
        if element_type in SKIP_ELEMENT_TYPES:
            continue

        text = _item_text(item, doc)
        if not text and element_type not in HEADING_ELEMENT_TYPES:
            continue

        prov = item.prov[0]
        page_number = int(prov.page_no)
        page_height = page_heights.get(page_number, 792.0)
        bbox = _bbox_to_top_left(prov.bbox, page_height=page_height)
        block_index = block_counters.get(page_number, 0)
        block_counters[page_number] = block_index + 1

        metadata: dict[str, Any] = {
            "docling_label": str(getattr(item, "label", "")),
            "element_type": element_type,
        }
        if element_type in CONTENT_ELEMENT_TYPES:
            metadata["line_count"] = text.count("\n") + 1

        elements.append(
            DocElement(
                element_index=element_index,
                element_type=element_type,
                text=text,
                page_number=page_number,
                block_index=block_index,
                bbox=bbox,
                heading_level=_heading_level_for_item(item, element_type),
                metadata=metadata,
            )
        )
        element_index += 1

    return elements


def elements_to_layout_pages(
    elements: list[DocElement],
    *,
    page_sizes: dict[int, tuple[float, float]],
) -> list[LayoutPage]:
    """Build LayoutPage/LayoutBlock structures from internal elements."""
    by_page: dict[int, list[DocElement]] = {}
    for element in elements:
        by_page.setdefault(element.page_number, []).append(element)

    pages: list[LayoutPage] = []
    for page_number in sorted(by_page):
        page_elements = sorted(
            by_page[page_number],
            key=lambda element: (element.block_index, element.element_index),
        )
        width, height = page_sizes.get(page_number, (612.0, 792.0))
        blocks = [
            LayoutBlock(
                page_number=page_number,
                block_index=element.block_index,
                text=element.text,
                bbox=element.bbox,
                metadata=dict(element.metadata),
            )
            for element in page_elements
        ]
        pages.append(
            rebuild_layout_page(
                LayoutPage(
                    page_number=page_number,
                    width=width,
                    height=height,
                    text="",
                    blocks=[],
                ),
                blocks,
            )
        )
    return pages


def docling_document_to_layout(
    doc: DoclingDocument,
) -> tuple[list[DocElement], list[LayoutPage]]:
    """Full conversion from DoclingDocument to elements and layout pages."""
    elements = docling_document_to_elements(doc)
    page_sizes = {
        page_no: (float(page.size.width), float(page.size.height))
        for page_no, page in doc.pages.items()
    }
    pages = elements_to_layout_pages(elements, page_sizes=page_sizes)
    return elements, pages
