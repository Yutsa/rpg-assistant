from rpg_ingest.raw.chunking import (
    build_chunks,
    chunk_block_signature,
    chunk_uniqueness_stats,
)
from rpg_ingest.raw.sections import detect_sections
from tests.fixtures.layout import make_block as _block, make_page as _page


def test_build_chunks_partitions_blocks_between_headings_on_same_page():
    pages = [
        _page(
            [
                _block(5, 0, "EN QUELQUES MOTS", font_size=14, bold=True, y0=10),
                _block(5, 1, "Résumé court.", font_size=11, y0=40),
                _block(5, 2, "FICHE TECHNIQUE", font_size=14, bold=True, y0=70),
                _block(5, 3, "Niveau 5", font_size=11, y0=100),
                _block(5, 4, "LES GRANDES LIGNES", font_size=13, bold=True, y0=130),
                _block(5, 5, "Contenu principal.", font_size=11, y0=160),
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
                _block(1, 1, "First paragraph.", font_size=11, y0=40),
                _block(1, 2, "Second paragraph.", font_size=11, y0=70),
            ]
        ),
        _page(
            [
                _block(2, 0, "Chapter 2", font_size=18, bold=True, y0=10),
                _block(2, 1, "Third paragraph.", font_size=11, y0=40),
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
