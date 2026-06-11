from rpg_assistant.ingestion.raw.chunking import (
    build_chunks,
    chunk_block_signature,
    chunk_uniqueness_stats,
)
from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.models.raw import BBox


def _block(
    page: int,
    index: int,
    text: str,
    *,
    font_size: float = 11.0,
    bold: bool = False,
    y0: float = 0.0,
) -> LayoutBlock:
    return LayoutBlock(
        page_number=page,
        block_index=index,
        text=text,
        bbox=BBox(x0=0, y0=y0, x1=100, y1=y0 + 20),
        metadata={
            "max_font_size": font_size,
            "avg_font_size": font_size,
            "is_bold": bold,
        },
    )


def _page(blocks: list[LayoutBlock]) -> LayoutPage:
    return LayoutPage(
        page_number=blocks[0].page_number,
        width=612,
        height=792,
        text="\n\n".join(block.text for block in blocks),
        blocks=blocks,
    )


def test_build_chunks_partitions_blocks_between_headings_on_same_page():
    pages = [
        _page(
            [
                _block(5, 0, "EN QUELQUES MOTS", font_size=14, bold=True, y0=10),
                _block(5, 1, "Résumé court.", y0=40),
                _block(5, 2, "FICHE TECHNIQUE", font_size=14, bold=True, y0=70),
                _block(5, 3, "Niveau 5", y0=100),
                _block(5, 4, "LES GRANDES LIGNES", font_size=13, bold=True, y0=130),
                _block(5, 5, "Contenu principal.", y0=160),
            ]
        )
    ]
    section_result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="camp_test",
        document_id="doc_test",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )

    assert len(chunks) == 3
    signatures = [chunk_block_signature(chunk) for chunk in chunks]
    assert len(set(signatures)) == 3
    assert chunk_uniqueness_stats(chunks)["duplicate_chunk_count"] == 0
    assert chunks[0].text == "Résumé court."
    assert chunks[1].text == "Niveau 5"
    assert chunks[2].text == "Contenu principal."


def test_build_chunks_covers_all_blocks_without_duplicates():
    pages = [
        _page(
            [
                _block(1, 0, "Chapter 1", font_size=18, bold=True, y0=10),
                _block(1, 1, "First paragraph.", y0=40),
                _block(1, 2, "Second paragraph.", y0=70),
            ]
        ),
        _page(
            [
                _block(2, 0, "Chapter 2", font_size=18, bold=True, y0=10),
                _block(2, 1, "Third paragraph.", y0=40),
            ]
        ),
    ]
    section_result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="camp_test",
        document_id="doc_test",
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
    )

    heading_positions = set(section_result.heading_anchors)
    referenced = {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }
    expected = {
        f"block_{page.page_number:03d}_{block.block_index:03d}"
        for page in pages
        for block in page.blocks
        if (page.page_number, block.block_index) not in heading_positions
    }
    assert referenced == expected
    assert chunk_uniqueness_stats(chunks)["chunk_unique_block_signature_ratio"] == 1.0
