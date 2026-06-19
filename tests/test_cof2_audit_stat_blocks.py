"""COF2 audit regressions — stat blocks (issues 5, 6 & 7)."""

from __future__ import annotations

from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks
from rpg_ingest.raw.stat_blocks.cof2 import Cof2StatBlockProfile
from tests.fixtures.cof2_audit_expectations import (
    CENTAURE_ABILITIES,
    FEE_ABILITIES,
    SOMBRE_FEE_ABILITIES,
)
from tests.fixtures.layout import make_block as _block, make_page as _page
from tests.fixtures.pipeline import run_raw_extraction_pipeline, stat_block_ability_titles


def _centaure_pages() -> list[LayoutPage]:
    """Long two-column fiche: narrative interrupt drops left-column abilities."""
    return [
        _page(
            [
                _block(16, 0, "W\nW", font_size=12, bold=True, y0=10, x0=42, x1=60),
                _block(
                    16,
                    1,
                    "CENTAURE | NC 3",
                    font_size=12,
                    bold=True,
                    y0=40,
                    x0=42,
                    x1=200,
                ),
                _block(
                    16,
                    2,
                    "AGI +2 | FOR +4 | CON +3 | INT +0 | PER +1 | CHA +0",
                    font_size=10,
                    y0=70,
                    x0=42,
                    x1=227,
                ),
                _block(
                    16,
                    5,
                    "HYBRIDE :\nLe centaure combine force humaine et vitesse équine.",
                    font_size=10,
                    bold=True,
                    y0=100,
                    x0=248,
                    x1=424,
                ),
                _block(
                    16,
                    6,
                    "DISCRET :\nLe centaure se fond dans la végétation.",
                    font_size=10,
                    bold=True,
                    y0=160,
                    x0=248,
                    x1=424,
                ),
                _block(
                    16,
                    7,
                    "Notes de terrain",
                    font_size=13,
                    bold=True,
                    y0=200,
                    x0=42,
                    x1=200,
                ),
                _block(
                    16,
                    3,
                    "ATTAQUE DOUBLE :\nLe centaure peut attaquer deux fois par round.",
                    font_size=10,
                    bold=True,
                    y0=250,
                    x0=42,
                    x1=227,
                ),
                _block(
                    16,
                    4,
                    "CHARGER :\nLe centaure fonce sur sa cible et la renverse.",
                    font_size=10,
                    bold=True,
                    y0=300,
                    x0=42,
                    x1=227,
                ),
            ],
            page_number=16,
            width=510,
            height=650,
        )
    ]


def _fee_pages() -> list[LayoutPage]:
    return [
        _page(
            [
                _block(15, 0, "W\nW", font_size=12, bold=True, y0=10, x0=42, x1=60),
                _block(
                    15,
                    1,
                    "FÉE | NC 2",
                    font_size=12,
                    bold=True,
                    y0=40,
                    x0=42,
                    x1=200,
                ),
                _block(
                    15,
                    2,
                    "AGI +4 | FOR -2 | CON +0 | INT +2 | PER +3 | CHA +4",
                    font_size=10,
                    y0=70,
                    x0=42,
                    x1=227,
                ),
                _block(
                    15,
                    6,
                    "RÉSISTANCE AUX DM :\nLa fée résiste aux dégâts magiques.",
                    font_size=10,
                    bold=True,
                    y0=100,
                    x0=248,
                    x1=424,
                ),
                _block(
                    15,
                    7,
                    "VOL :\nLa fée vole silencieusement.",
                    font_size=10,
                    bold=True,
                    y0=150,
                    x0=248,
                    x1=424,
                ),
                _block(
                    15,
                    8,
                    "Notes de terrain",
                    font_size=13,
                    bold=True,
                    y0=200,
                    x0=42,
                    x1=200,
                ),
                _block(
                    15,
                    3,
                    "CHARME PERSONNE :\nLa fée peut charmer une créature humanoïde.",
                    font_size=10,
                    bold=True,
                    y0=250,
                    x0=42,
                    x1=227,
                ),
                _block(
                    15,
                    4,
                    "DISTRACTION :\nLa fée distrait ses adversaires par des illusions.",
                    font_size=10,
                    bold=True,
                    y0=300,
                    x0=42,
                    x1=227,
                ),
                _block(
                    15,
                    5,
                    "ÉTERNUEMENT :\nLa fée provoque un éternuement magique.",
                    font_size=10,
                    bold=True,
                    y0=350,
                    x0=42,
                    x1=227,
                ),
            ],
            page_number=15,
            width=510,
            height=650,
        )
    ]


def _sombre_fee_pages() -> list[LayoutPage]:
    return [
        _page(
            [
                _block(19, 0, "W\nW", font_size=12, bold=True, y0=10, x0=42, x1=60),
                _block(
                    19,
                    1,
                    "SOMBRE FÉE (ARACHNOÏDE) | NC 4",
                    font_size=12,
                    bold=True,
                    y0=40,
                    x0=42,
                    x1=280,
                ),
                _block(
                    19,
                    2,
                    "AGI +3 | FOR +1 | CON +2 | INT +1 | PER +2 | CHA +0",
                    font_size=10,
                    y0=70,
                    x0=42,
                    x1=227,
                ),
                _block(
                    19,
                    6,
                    "MAÎTRE DES TOILES :\nElle contrôle les toiles sur une large zone.",
                    font_size=10,
                    bold=True,
                    y0=100,
                    x0=248,
                    x1=424,
                ),
                _block(
                    19,
                    7,
                    "POISON :\nSa morsure injecte un venin paralysant.",
                    font_size=10,
                    bold=True,
                    y0=150,
                    x0=248,
                    x1=424,
                ),
                _block(
                    19,
                    8,
                    "CAMOUFLAGE :\nElle se fond dans les ombres.",
                    font_size=10,
                    bold=True,
                    y0=200,
                    x0=248,
                    x1=424,
                ),
                _block(
                    19,
                    9,
                    "Notes de terrain",
                    font_size=13,
                    bold=True,
                    y0=240,
                    x0=42,
                    x1=200,
                ),
                _block(
                    19,
                    3,
                    "TOILE :\nLa sombre fée projette une toile collante.",
                    font_size=10,
                    bold=True,
                    y0=280,
                    x0=42,
                    x1=227,
                ),
                _block(
                    19,
                    4,
                    "PATTES D'ARAIGNÉE :\nSes pattes transpercent l'armure.",
                    font_size=10,
                    bold=True,
                    y0=330,
                    x0=42,
                    x1=227,
                ),
            ],
            page_number=19,
            width=510,
            height=650,
        )
    ]


def _ability_titles_from_spans(pages: list[LayoutPage], name_substr: str) -> list[str]:
    profile = Cof2StatBlockProfile()
    stat_result = annotate_stat_blocks(pages, profile)
    span = next(
        span
        for span in stat_result.spans
        if any(name_substr in block.text for block in span.blocks)
    )
    parsed = profile.parse_span(span)
    return [ability.title for ability in parsed.abilities]


def test_centaure_parses_all_abilities_from_span():
    """Audit issue 5 — CENTAURE must expose all four named abilities."""
    pages = _centaure_pages()
    titles = _ability_titles_from_spans(pages, "CENTAURE")
    assert titles == list(CENTAURE_ABILITIES)


def test_centaure_chunk_metadata_includes_all_abilities():
    """Audit issue 5 — pipeline chunk metadata must list all CENTAURE abilities."""
    result = run_raw_extraction_pipeline(
        _centaure_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_centaure_audit",
    )
    stat_chunks = [c for c in result.chunks if c.chunk_type_hint == "stat_block"]
    assert stat_chunks
    titles = stat_block_ability_titles(result.chunks, "CENTAURE")
    assert titles == list(CENTAURE_ABILITIES)


def test_fee_parses_all_abilities_from_span():
    """Audit issue 6 — FÉE must expose all five named abilities."""
    pages = _fee_pages()
    titles = _ability_titles_from_spans(pages, "FÉE")
    assert titles == list(FEE_ABILITIES)


def test_fee_chunk_metadata_includes_all_abilities():
    """Audit issue 6 — pipeline chunk metadata must list all FÉE abilities."""
    result = run_raw_extraction_pipeline(
        _fee_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_fee_audit",
    )
    titles = stat_block_ability_titles(result.chunks, "FÉE")
    assert titles == list(FEE_ABILITIES)


def test_sombre_fee_parses_all_abilities_from_span():
    """Audit issue 7 — SOMBRE FÉE must expose all five named abilities."""
    pages = _sombre_fee_pages()
    titles = _ability_titles_from_spans(pages, "SOMBRE FÉE")
    assert titles == list(SOMBRE_FEE_ABILITIES)


def test_sombre_fee_chunk_metadata_includes_all_abilities():
    """Audit issue 7 — pipeline chunk metadata must list all SOMBRE FÉE abilities."""
    result = run_raw_extraction_pipeline(
        _sombre_fee_pages(),
        campaign_id="dernier-faelys",
        document_id="doc_sombre_fee_audit",
    )
    titles = stat_block_ability_titles(result.chunks, "SOMBRE FÉE")
    assert titles == list(SOMBRE_FEE_ABILITIES)


def _collapsed_fee_pages() -> list[LayoutPage]:
    """Single merged block like real PDF extraction (all abilities inline)."""
    return [
        _page(
            [
                _block(
                    15,
                    0,
                    (
                        "FÉE | NC 0\n"
                        "TAILLE MINUSCULE | AGI +4* | CON -2 | FOR -5 | PER +2* | | "
                        "CHA +1* | INT +0 | VOL +4 | (S) DEF 20 (V) PV 5 (I) Init. 15 "
                        "CHARME PERSONNE (L) : Une cible humanoïde doit réussir un test. "
                        "DISTRACTION (G) : La fée danse et fait sa coquette. "
                        "ÉTERNUEMENT (M) : La fée volette autour de sa cible. "
                        "RÉSISTANCE AUX DM : La fée a une RD 5. "
                        "VOL : La créature est capable de voler."
                    ),
                    font_size=10,
                    bold=False,
                    y0=40,
                    x0=42,
                    x1=227,
                ),
            ],
            page_number=15,
            width=510,
            height=650,
        )
    ]


def test_fee_parses_inline_abilities_from_collapsed_block():
    """Real PDFs may merge header, stats and abilities into one block."""
    pages = _collapsed_fee_pages()
    titles = _ability_titles_from_spans(pages, "FÉE")
    assert titles == list(FEE_ABILITIES)


def test_sombre_fee_parses_inline_abilities_with_typographic_apostrophe():
    """Real Faelys PDF uses U+2019 in PATTES D'ARAIGNÉE inside collapsed inline text."""
    collapsed = (
        "SOMBRE FÉE (ARACHNOÏDE) | NC 3\n"
        "AGI +2* | CON +1 | (S) DEF 16 (V) PV 30 (I) Init. 11 "
        "TOILE (M) : Sur un test d'attaque réussi. "
        "MAÎTRE DES TOILES : L'arachnoïde peut se déplacer. "
        "PATTES D\u2019ARAIGNÉE : L'arachnoïde peut escalader. "
        "POISON : En cas d'échec. "
        "CAMOUFLAGE : L'arachnoïde obtient un bonus."
    )
    pages = [
        _page(
            [
                _block(
                    19,
                    0,
                    collapsed,
                    font_size=10,
                    bold=False,
                    y0=40,
                    x0=42,
                    x1=424,
                ),
            ],
            page_number=19,
            width=510,
            height=650,
        )
    ]
    titles = _ability_titles_from_spans(pages, "SOMBRE FÉE")
    assert titles == list(SOMBRE_FEE_ABILITIES)
