from rpg_assistant.ingestion.raw.chunking import build_chunks
from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.ingestion.raw.stat_blocks import annotate_stat_blocks
from rpg_assistant.ingestion.raw.stat_blocks.cof2 import Cof2StatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.registry import resolve_profile
from rpg_assistant.ingestion.raw.stat_blocks.text_utils import strip_layout_glyphs
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


def _cof2_pages() -> list[LayoutPage]:
    return [
        _page(
            [
                _block(15, 0, "W\nW", font_size=12, bold=True, y0=10),
                _block(
                    15,
                    1,
                    "AZULRIA, PRÊTRESSE 7 | NC 4",
                    font_size=12,
                    bold=True,
                    y0=40,
                ),
                _block(
                    15,
                    2,
                    "AGI +1 | FOR +3 | CON +2 | INT +0 | PER +1 | CHA +4",
                    font_size=10,
                    y0=70,
                ),
                _block(
                    15,
                    3,
                    "PASSAGE DANS LA PIERRE :\nDeux fois par jour, la momie peut se déplacer.",
                    font_size=10,
                    bold=True,
                    y0=100,
                ),
                _block(15, 4, "W\nW\nTALESS RHANN", font_size=12, bold=True, y0=200),
                _block(
                    15,
                    5,
                    "AGI +0 | FOR +2 | CON +1 | INT +0 | PER +2 | CHA +1",
                    font_size=10,
                    y0=230,
                ),
            ]
        )
    ]


def test_cof2_false_heading_azulria():
    profile = Cof2StatBlockProfile()
    block = _block(15, 1, "AZULRIA, PRÊTRESSE 7 | NC 4", font_size=12, bold=True)
    page_blocks = _cof2_pages()[0].blocks

    assert profile.is_false_heading(block, page_blocks, 1) is True


def test_cof2_false_heading_with_icon_glyphs():
    profile = Cof2StatBlockProfile()
    raw = "W\nW\nAZULRIA, PRÊTRESSE 7 | NC 4"
    normalized = strip_layout_glyphs(raw)

    assert "W" not in normalized.split()
    assert "AZULRIA" in normalized


def test_cof2_parse_attributes_and_nc():
    profile = Cof2StatBlockProfile()
    pages = _cof2_pages()
    stat_result = annotate_stat_blocks(pages, profile)
    azulria_span = next(
        span
        for span in stat_result.spans
        if any("AZULRIA" in block.text for block in span.blocks)
    )
    parsed = profile.parse_span(azulria_span)

    assert parsed.name == "AZULRIA"
    assert parsed.subtitle == "PRÊTRESSE 7"
    assert parsed.nc == 4
    assert parsed.attributes["AGI"] == 1
    assert parsed.attributes["FOR"] == 3
    assert parsed.abilities[0].title == "PASSAGE DANS LA PIERRE"


def test_cof2_parse_per_and_vol_separately():
    profile = Cof2StatBlockProfile()
    pages = [
        _page(
            [
                _block(15, 0, "W\nW", font_size=12, bold=True, y0=10),
                _block(
                    15,
                    1,
                    "AZULRIA, PRÊTRESSE 7 | NC 4",
                    font_size=12,
                    bold=True,
                    y0=40,
                ),
                _block(15, 2, "HUMAINE", font_size=8, bold=True, y0=60),
                _block(
                    15,
                    3,
                    "| AGI +1 | CON +2 | FOR +1 | PER +0 |\n| CHA +0 | INT +0 | VOL +3 |",
                    font_size=10,
                    y0=70,
                ),
            ]
        )
    ]
    stat_result = annotate_stat_blocks(pages, profile)
    azulria_span = next(
        span
        for span in stat_result.spans
        if any("AZULRIA" in block.text for block in span.blocks)
    )
    parsed = profile.parse_span(azulria_span)

    assert parsed.attributes["PER"] == 0
    assert parsed.attributes["VOL"] == 3
    assert parsed.attributes["AGI"] == 1
    assert parsed.attributes["CON"] == 2
    assert parsed.attributes["FOR"] == 1
    assert parsed.attributes["CHA"] == 0
    assert parsed.attributes["INT"] == 0


def test_cof2_detect_span_multiblock():
    profile = Cof2StatBlockProfile()
    stat_result = annotate_stat_blocks(_cof2_pages(), profile)

    assert len(stat_result.spans) == 2
    assert len(stat_result.spans[0].blocks) >= 3
    roles = {block.metadata.get("stat_block_role") for block in stat_result.spans[0].blocks}
    assert "header" in roles
    assert "stats" in roles


def test_sections_excludes_stat_block_names():
    profile = Cof2StatBlockProfile()
    pages = annotate_stat_blocks(_cof2_pages(), profile).pages
    result = detect_sections(pages, campaign_id="momie", document_id="doc_test", profile=profile)
    titles = [section.title for section in result.sections]

    assert not any("AZULRIA" in title for title in titles)
    assert not any("TALESS RHANN" in title for title in titles)


def test_chunk_metadata_stat_block():
    profile = Cof2StatBlockProfile()
    stat_result = annotate_stat_blocks(_cof2_pages(), profile)
    pages = stat_result.pages
    section_result = detect_sections(
        pages, campaign_id="momie", document_id="doc_test", profile=profile
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="momie",
        document_id="doc_test",
        heading_anchors=section_result.heading_anchors,
        stat_spans=stat_result.spans,
        profile=profile,
    )

    stat_chunks = [chunk for chunk in chunks if chunk.chunk_type_hint == "stat_block"]
    assert stat_chunks
    azulria_chunk = next(
        chunk for chunk in stat_chunks if chunk.metadata.get("stat_block", {}).get("name") == "AZULRIA"
    )
    assert azulria_chunk.metadata["stat_block"]["nc"] == 4
    assert "W" not in azulria_chunk.text


def test_resolve_profile_by_game_system():
    profile = resolve_profile("cof2", None)
    assert profile.profile_id == "cof2"


def test_resolve_profile_auto_detect():
    profile = resolve_profile("", _cof2_pages())
    assert profile.profile_id == "cof2"
