from rpg_ingest.raw.chunking import _deduplicate_stat_block_chunks, build_chunks
from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.sections import detect_sections
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks
from rpg_ingest.raw.stat_blocks.cof2 import Cof2StatBlockProfile
from rpg_ingest.raw.stat_blocks.registry import resolve_profile
from rpg_ingest.raw.stat_blocks.text_utils import strip_layout_glyphs
from rpg_core.models.raw import ChunkRecord, SourceSpan
from rpg_core.storage.ids import page_block_id
from tests.fixtures.layout import make_block as _block, make_page as _page


def _stat_chunk(
    *,
    chunk_id: str,
    section_id: str,
    span_id: str,
    name: str,
    block_page: int,
    block_indices: list[int],
) -> ChunkRecord:
    return ChunkRecord(
        id=chunk_id,
        campaign_id="momie",
        document_id="doc_test",
        section_id=section_id,
        page_start=block_page,
        page_end=block_page,
        text=name,
        chunk_type_hint="stat_block",
        source_spans=[
            SourceSpan(
                page=block_page,
                page_block_ids=[
                    page_block_id("doc_test", block_page, idx) for idx in block_indices
                ],
            )
        ],
        metadata={
            "stat_block_span_id": span_id,
            "stat_block": {"name": name, "game_system": "cof2"},
        },
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
    assert parsed.abilities[0].text.startswith("Deux fois par jour")


def _taless_pages() -> list[LayoutPage]:
    return [
        _page(
            [
                _block(15, 0, "W\nW\nTALESS RHANN", font_size=12, bold=True, y0=10),
                _block(
                    15,
                    1,
                    "Voir le profil de momie (Livre de règles, COF)\n"
                    "Grâce à son talisman, Taless a plusieurs pouvoirs supplémentaires.",
                    font_size=10,
                    y0=40,
                ),
                _block(
                    15,
                    2,
                    "TORNADE DE SABLE :\n"
                    "Deux fois par jour, sur 10 m de rayon autour de lui, des rafales de sable perturbent toute\n"
                    "action. Toute créature voulant l'attaquer subit un dé malus.",
                    font_size=10,
                    bold=True,
                    y0=80,
                ),
                _block(
                    15,
                    3,
                    "MALÉDICTION PROPHÉTIQUE :\n"
                    "Une fois par lune, la momie peut proférer une malédiction sur toutes les personnes l'entourant\n"
                    "dans un rayon de 10 m. En cas d'échec, c'est la mort assurée à la prochaine pleine lune.",
                    font_size=10,
                    bold=True,
                    y0=140,
                ),
                _block(
                    15,
                    4,
                    "PASSAGE DANS LA PIERRE :\n"
                    "Deux fois par jour, la momie peut utiliser le pouvoir de passe-muraille et se déplacer à\n"
                    "travers la matière sur 10 m dans toutes les directions.",
                    font_size=10,
                    bold=True,
                    y0=220,
                ),
                _block(
                    15,
                    5,
                    "ANIMATION DES MORTS :\n"
                    "Une fois par jour, la momie peut animer 12 cadavres humanoïdes de taille moyenne. Ils se\n"
                    "comportent comme des zombies (cf. le profil dans le livre de règles de COF).",
                    font_size=10,
                    bold=True,
                    y0=300,
                ),
            ]
        )
    ]


def test_cof2_parse_taless_abilities():
    profile = Cof2StatBlockProfile()
    stat_result = annotate_stat_blocks(_taless_pages(), profile)
    taless_span = next(
        span
        for span in stat_result.spans
        if any("TALESS RHANN" in block.text for block in span.blocks)
    )
    parsed = profile.parse_span(taless_span)

    assert parsed.name == "TALESS RHANN"
    assert parsed.rulebook_reference is not None
    assert parsed.rulebook_reference.profile_name == "momie"
    assert len(parsed.abilities) == 4
    by_title = {ability.title: ability.text for ability in parsed.abilities}
    assert "rafales de sable" in by_title["TORNADE DE SABLE"]
    assert "pleine lune" in by_title["MALÉDICTION PROPHÉTIQUE"]
    assert "passe-muraille" in by_title["PASSAGE DANS LA PIERRE"]
    assert "12 cadavres" in by_title["ANIMATION DES MORTS"]
    assert all(text.strip() for text in by_title.values())


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
        content_only_section_ids=section_result.content_only_section_ids,
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


def test_stat_block_dedup_keeps_header_section():
    pages = _taless_pages()
    for block in pages[0].blocks:
        if "TALESS RHANN" in block.text:
            block.metadata["stat_block_id"] = "sb_taless"
            block.metadata["stat_block_role"] = "header"
        elif block.metadata.get("stat_block_role") is None:
            block.metadata["stat_block_id"] = "sb_taless"
            block.metadata["stat_block_role"] = "body"

    duplicate_a = _stat_chunk(
        chunk_id="chunk_015_022",
        section_id="sec_sand",
        span_id="sb_taless",
        name="TALESS RHANN",
        block_page=15,
        block_indices=[0, 1],
    )
    duplicate_b = _stat_chunk(
        chunk_id="chunk_015_024",
        section_id="sec_arcanes",
        span_id="sb_taless",
        name="TALESS RHANN",
        block_page=15,
        block_indices=[2, 3, 4, 5],
    )
    deduped = _deduplicate_stat_block_chunks(
        [duplicate_a, duplicate_b],
        pages,
    )
    taless_chunks = [
        chunk
        for chunk in deduped
        if chunk.metadata.get("stat_block", {}).get("name") == "TALESS RHANN"
    ]
    assert len(taless_chunks) == 1
    assert taless_chunks[0].id == "chunk_015_024"
    assert taless_chunks[0].section_id == "sec_sand"


def _fleurs_gardiennes_pages() -> list[LayoutPage]:
    return [
        _page(
            [
                _block(
                    10,
                    0,
                    "Du haut du sanctuaire, les PJ découvrent le val de l'Orm.",
                    font_size=10,
                    y0=40,
                ),
                _block(
                    10,
                    1,
                    "Un cercle de fleurs géantes entoure la colline.",
                    font_size=10,
                    y0=70,
                ),
                _block(10, 2, "W\nW\nLES FLEURS GARDIENNES", font_size=12, bold=True, y0=100),
                _block(
                    10,
                    3,
                    "Utilisez le profil du serpent constricteur que vous trouverez "
                    "dans le livre de règles de COF.",
                    font_size=10,
                    y0=130,
                ),
                _block(
                    10,
                    4,
                    "L'étreinte ne cause pas de DM. Immobile sur terre, cette plante dispose de la capacité Vol.",
                    font_size=10,
                    y0=160,
                ),
            ]
        )
    ]


def test_cof2_parse_fleurs_gardiennes_rulebook_reference():
    profile = Cof2StatBlockProfile()
    stat_result = annotate_stat_blocks(_fleurs_gardiennes_pages(), profile)
    fleurs_span = next(
        span
        for span in stat_result.spans
        if any("FLEURS GARDIENNES" in block.text for block in span.blocks)
    )
    parsed = profile.parse_span(fleurs_span)

    assert parsed.name == "LES FLEURS GARDIENNES"
    assert parsed.rulebook_reference is not None
    assert parsed.rulebook_reference.profile_name == "serpent constricteur"
    assert "étreinte ne cause pas de DM" in parsed.raw_text


def test_cof2_parse_fleurs_gardiennes_rulebook_reference_multiline():
    profile = Cof2StatBlockProfile()
    pages = [
        _page(
            [
                _block(10, 0, "W\nW\nLES FLEURS GARDIENNES", font_size=12, bold=True, y0=10),
                _block(
                    10,
                    1,
                    "Utilisez le profil du serpent constricteur que\n"
                    "vous trouverez dans le livre de règles de COF.",
                    font_size=10,
                    y0=40,
                ),
            ]
        )
    ]
    stat_result = annotate_stat_blocks(pages, profile)
    parsed = profile.parse_span(stat_result.spans[0])

    assert parsed.rulebook_reference is not None
    assert parsed.rulebook_reference.profile_name == "serpent constricteur"
