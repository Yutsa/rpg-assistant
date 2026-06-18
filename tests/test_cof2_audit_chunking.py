"""COF2 audit regressions — chunking (issues 1, 2, 8, 9 & 10)."""

from __future__ import annotations

from rpg_ingest.raw.block_merging import merge_fragmented_blocks
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, rebuild_layout_page
from rpg_ingest.raw.stat_blocks import resolve_profile
from rpg_core.models.raw import BBox
from tests.fixtures.cof2_audit_expectations import (
    FAELYS_CREDITS_MARKERS,
    FAELYS_CREDITS_SECTION,
    FAELYS_INTRO_MARKERS,
    FAELYS_INTRO_SECTION,
    MOMIE_CREDITS_MARKERS,
    MOMIE_SYNOPSIS_MARKERS,
    MOMIE_SYNOPSIS_SECTION,
)
from tests.fixtures.layout import make_block as _layout_block, make_page as _layout_page
from tests.fixtures.pipeline import (
    chunk_texts_for_section,
    contains_any,
    run_raw_extraction_pipeline,
    section_by_title,
)


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


def _momie_cover_credits_pages() -> list[LayoutPage]:
    """Synopsis p.2 and credits p.4 under the same section (no CRÉDITS heading on p.4)."""
    page_two = [
        _block(
            2,
            0,
            "LA MALÉDICTION DE LA MOMIE",
            x0=42,
            y0=80,
            x1=400,
            y1=110,
            font_size=18,
            bold=True,
        ),
        _block(
            2,
            1,
            "Une malédiction pèse sur la région. Lors d'une soirée mondaine, la momie "
            "s'éveille et seme le chaos parmi les convives.",
            x0=42,
            y0=130,
            x1=420,
            y1=280,
        ),
    ]
    page_three = [
        _block(3, 0, "2", x0=250, y0=600, x1=260, y1=615, font_size=8),
    ]
    page_four = [
        _block(
            4,
            0,
            "L'équipe de Black Book Éditions vous remercie. Tous droits réservés.",
            x0=42,
            y0=80,
            x1=420,
            y1=200,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=2, width=510, height=650, text="", blocks=[]),
            page_two,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=3, width=510, height=650, text="", blocks=[]),
            page_three,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=4, width=510, height=650, text="", blocks=[]),
            page_four,
        ),
    ]


def _faelys_credits_intro_pages() -> list[LayoutPage]:
    """Credits p.4 absorb intro p.5 before EN QUELQUES MOTS on p.6."""
    page_four = [
        _block(
            4,
            0,
            "CRÉDITS",
            x0=42,
            y0=55,
            x1=150,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            4,
            1,
            "L'équipe de Black Book Éditions vous remercie. Tous droits réservés.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
    ]
    page_five = [
        _block(
            5,
            0,
            "Le bois d'Astréis est un lieu mystérieux où les fées règnent en maîtresses.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
            font_size=11,
        ),
    ]
    page_six = [
        _block(
            6,
            0,
            "EN QUELQUES MOTS",
            x0=78,
            y0=219,
            x1=190,
            y1=232,
            font_size=11.5,
            bold=True,
        ),
        _block(
            6,
            1,
            "Les PJ sont invités à explorer ce domaine féérique.",
            x0=43,
            y0=250,
            x1=227,
            y1=350,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=4, width=510, height=650, text="", blocks=[]),
            page_four,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=5, width=510, height=650, text="", blocks=[]),
            page_five,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=6, width=510, height=650, text="", blocks=[]),
            page_six,
        ),
    ]


def _faelys_credits_intro_merge_pages() -> list[LayoutPage]:
    """Cross-page hyphenation-style merge between credits trail and intro body."""
    page_four = [
        _block(
            4,
            0,
            "CRÉDITS",
            x0=42,
            y0=55,
            x1=150,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            4,
            1,
            "L'équipe de Black Book Éditions vous remercie pour votre",
            x0=42,
            y0=500,
            x1=227,
            y1=560,
        ),
    ]
    page_five = [
        _block(
            5,
            0,
            "confiance et vous souhaite bon jeu. Tous droits réservés.",
            x0=42,
            y0=45,
            x1=227,
            y1=103,
        ),
        _block(
            5,
            1,
            "Le bois d'Astréis est un lieu mystérieux.",
            x0=42,
            y0=120,
            x1=227,
            y1=200,
            font_size=11,
        ),
        _block(
            5,
            2,
            "EN QUELQUES MOTS",
            x0=78,
            y0=219,
            x1=190,
            y1=232,
            font_size=11.5,
            bold=True,
        ),
        _block(
            5,
            3,
            "Les PJ explorent le domaine féérique.",
            x0=43,
            y0=250,
            x1=227,
            y1=350,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=4, width=510, height=650, text="", blocks=[]),
            page_four,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=5, width=510, height=650, text="", blocks=[]),
            page_five,
        ),
    ]


def test_momie_synopsis_chunk_does_not_include_credits():
    """Audit issue 1 — synopsis p.2 must not mix with credits p.4."""
    result = run_raw_extraction_pipeline(
        _momie_cover_credits_pages(),
        campaign_id="momie",
        document_id="doc_momie_audit",
    )

    synopsis_texts = chunk_texts_for_section(
        result.chunks, result.sections, MOMIE_SYNOPSIS_SECTION
    )
    assert synopsis_texts, f"Expected chunks for {MOMIE_SYNOPSIS_SECTION!r}"
    synopsis_text = "\n".join(synopsis_texts)
    assert contains_any(synopsis_text, MOMIE_SYNOPSIS_MARKERS)
    assert not contains_any(synopsis_text, MOMIE_CREDITS_MARKERS)

    for chunk in result.chunks:
        if chunk.page_start <= 2 and chunk.page_end >= 4:
            text = chunk.text
            assert not (
                contains_any(text, MOMIE_SYNOPSIS_MARKERS)
                and contains_any(text, MOMIE_CREDITS_MARKERS)
            ), "Chunk must not span synopsis and credits across pages 2 and 4"


def test_faelys_credits_not_merged_with_intro():
    """Audit issue 2 — credits p.4 must not include intro p.5."""
    result = run_raw_extraction_pipeline(
        _faelys_credits_intro_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_faelys_audit",
    )

    credits_texts = chunk_texts_for_section(
        result.chunks, result.sections, FAELYS_CREDITS_SECTION
    )
    assert credits_texts
    credits_text = "\n".join(credits_texts)
    assert contains_any(credits_text, FAELYS_CREDITS_MARKERS)
    assert not contains_any(credits_text, FAELYS_INTRO_MARKERS)

    intro_texts = chunk_texts_for_section(
        result.chunks, result.sections, FAELYS_INTRO_SECTION
    )
    assert intro_texts
    intro_text = "\n".join(intro_texts)
    assert contains_any(intro_text, FAELYS_INTRO_MARKERS)
    assert not contains_any(intro_text, FAELYS_CREDITS_MARKERS)


def test_faelys_cross_page_merge_does_not_join_credits_with_intro():
    """Audit issue 2 — block_merging must not fuse credits trail with intro body."""
    pages = _faelys_credits_intro_merge_pages()
    profile = resolve_profile("cof2", pages)
    merged = merge_fragmented_blocks(pages, profile=profile).pages

    page_five_blocks = merged[1].blocks
    intro_blocks = [block for block in page_five_blocks if "Astréis" in block.text]
    assert intro_blocks, "Expected intro block on page 5"
    assert "Black Book" not in intro_blocks[0].text

    result = run_raw_extraction_pipeline(
        pages,
        campaign_id="dernier-faelys",
        document_id="doc_faelys_merge_audit",
    )
    credits_chunks = [
        chunk for chunk in result.chunks if contains_any(chunk.text, FAELYS_CREDITS_MARKERS)
    ]
    intro_chunks = [
        chunk for chunk in result.chunks if contains_any(chunk.text, FAELYS_INTRO_MARKERS)
    ]
    assert credits_chunks, "Credits text must land in at least one chunk"
    assert intro_chunks, "Intro text must land in at least one chunk"
    for chunk in result.chunks:
        assert not (
            contains_any(chunk.text, FAELYS_CREDITS_MARKERS)
            and contains_any(chunk.text, FAELYS_INTRO_MARKERS)
        ), "No chunk should mix credits and intro markers"


def _faelys_palace_bridge_pages() -> list[LayoutPage]:
    """Palace text on p.10 must not jump to p.12 when p.11 has narrative body."""
    page_ten = [
        _block(
            10,
            0,
            "Le palais des fleurs de la reine Épitialm",
            x0=42,
            y0=55,
            x1=300,
            y1=72,
            font_size=14,
            bold=True,
        ),
        _block(
            10,
            1,
            "La reine du val de l'Orm vit sur une colline couverte de hautes herbes.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
    ]
    page_eleven = [
        _block(
            11,
            0,
            "Une fois que les PJ ont expliqué la raison de leur venue, la reine s'exprime doucement.",
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
            "s'exprime d'une voix plus douce et énonce l'énigme suivante :",
            x0=42,
            y0=80,
            x1=227,
            y1=120,
        ),
        _block(
            12,
            1,
            "« Dans les champs repoussés sous la terre sans famille. »",
            x0=42,
            y0=130,
            x1=227,
            y1=200,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=10, width=510, height=650, text="", blocks=[]),
            page_ten,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=11, width=510, height=650, text="", blocks=[]),
            page_eleven,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=12, width=510, height=650, text="", blocks=[]),
            page_twelve,
        ),
    ]


def _mille_pattes_truncation_pages() -> list[LayoutPage]:
  return [
      _layout_page(
          [
              _layout_block(
                  12,
                  0,
                  "MILLE-PATTES | NC 3",
                  font_size=12,
                  bold=True,
                  y0=40,
                  x0=248,
                  x1=424,
              ),
              _layout_block(
                  12,
                  1,
                  "AGI +4 | FOR +3 | CON +3 | PER +2 | CHA -4 | INT -4 | VOL +0",
                  font_size=10,
                  y0=70,
                  x0=248,
                  x1=424,
              ),
              _layout_block(
                  12,
                  2,
                  "Pinces +6 · DM 2d6+3+ poison (2d6, difficulté",
                  font_size=10,
                  y0=100,
                  x0=248,
                  x1=424,
              ),
              _layout_block(
                  12,
                  3,
                  "12 pour ½ DM)",
                  font_size=10,
                  y0=120,
                  x0=248,
                  x1=424,
              ),
          ],
          page_number=12,
          width=510,
          height=650,
      )
  ]


def _centaure_column_pages() -> list[LayoutPage]:
    page_fifteen = [
        _block(
            15,
            0,
            "Les fées connaissent les éléments suivants.",
            x0=42,
            y0=46,
            x1=227,
            y1=100,
        ),
        _block(
            15,
            1,
            "Les centaures",
            x0=248,
            y0=48,
            x1=400,
            y1=65,
            font_size=13,
            bold=True,
        ),
        _block(
            15,
            2,
            "Cette tribu sauvage est dirigée par Homade.",
            x0=248,
            y0=80,
            x1=424,
            y1=120,
        ),
    ]
    page_sixteen = [
        _block(
            16,
            0,
            "Les centaures du val de l'Orm sont des chasseurs invétérés.",
            x0=42,
            y0=80,
            x1=227,
            y1=200,
        ),
        _block(
            16,
            1,
            "Les champs repoussés",
            x0=248,
            y0=300,
            x1=400,
            y1=318,
            font_size=13,
            bold=True,
        ),
        _block(
            16,
            2,
            "Le blé sauvage qui pousse ici donne une teinte dorée à la plaine.",
            x0=248,
            y0=330,
            x1=424,
            y1=420,
        ),
    ]
    return [
        rebuild_layout_page(
            LayoutPage(page_number=15, width=510, height=650, text="", blocks=[]),
            page_fifteen,
        ),
        rebuild_layout_page(
            LayoutPage(page_number=16, width=510, height=650, text="", blocks=[]),
            page_sixteen,
        ),
    ]


def test_faelys_palace_chunk_includes_page_eleven():
    """Audit issue 8 — narrative on p.11 must not be skipped when section continues."""
    result = run_raw_extraction_pipeline(
        _faelys_palace_bridge_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_faelys_bridge",
    )
    all_text = "\n".join(chunk.text for chunk in result.chunks)
    assert "colline couverte" in all_text
    assert "raison de leur venue" in all_text
    assert "énigme suivante" in all_text
    bridging = [
        chunk
        for chunk in result.chunks
        if chunk.page_start <= 10 and chunk.page_end >= 12
    ]
    for chunk in bridging:
        pages = {span.page for span in chunk.source_spans}
        assert 11 in pages, f"Chunk {chunk.id} bridges p.10–12 but omits p.11"


def test_mille_pattes_stat_block_not_split():
    """Audit issue 9 — MILLE-PATTES fiche must stay in one stat chunk."""
    result = run_raw_extraction_pipeline(
        _mille_pattes_truncation_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_mille_pattes_audit",
    )
    stat_chunks = [
        chunk for chunk in result.chunks if "MILLE-PATTES" in chunk.text
    ]
    assert len(stat_chunks) == 1
    assert "12 pour" in stat_chunks[0].text
    assert "difficulté" in stat_chunks[0].text
    orphan_fragments = [
        chunk for chunk in result.chunks if chunk.text.strip() == "12 pour ½ DM)"
    ]
    assert not orphan_fragments


def test_centaure_narrative_stays_in_centaures_section():
    """Audit issue 10 — left-column centaure narrative belongs to Les centaures."""
    result = run_raw_extraction_pipeline(
        _centaure_column_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_centaure_column",
    )
    centaures = section_by_title(result.sections, "Les centaures")
    champs = section_by_title(result.sections, "Les champs repoussés")
    centaure_texts = chunk_texts_for_section(
        result.chunks, result.sections, "Les centaures"
    )
    champs_texts = chunk_texts_for_section(
        result.chunks, result.sections, "Les champs repoussés"
    )
    assert any("chasseurs invétérés" in text for text in centaure_texts)
    assert not any("chasseurs invétérés" in text for text in champs_texts)
    assert centaures.id != champs.id
