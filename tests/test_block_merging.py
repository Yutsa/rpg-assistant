from rpg_assistant.ingestion.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.models.raw import BBox


def _block(
    page_number: int,
    block_index: int,
    text: str,
    *,
    x0: float = 51.0,
    x1: float = 218.8,
    y0: float = 100.0,
    y1: float = 120.0,
    font_size: float = 9.5,
    bold: bool = False,
    italic: bool = False,
) -> LayoutBlock:
    return LayoutBlock(
        page_number=page_number,
        block_index=block_index,
        text=text,
        bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
        metadata={
            "line_count": text.count("\n") + 1,
            "max_font_size": font_size,
            "avg_font_size": font_size,
            "is_bold": bold,
            "is_italic": italic,
        },
    )


def _page(blocks: list[LayoutBlock]) -> LayoutPage:
    return LayoutPage(
        page_number=blocks[0].page_number if blocks else 1,
        width=432.0,
        height=596.0,
        text="\n\n".join(block.text for block in blocks),
        blocks=blocks,
    )


def test_hyphenation_merge_rejoins_split_word():
    blocks = [
        _block(14, 0, "La créature morte‑vi‑\nvante se retourne vers vous et vous ressen‑", y0=45.5, y1=137.5),
        _block(14, 1, "tez immédiatement une", x0=123.0, y0=136.8, y1=148.9),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 1
    assert len(result.pages[0].blocks) == 1
    assert "vous ressentez immédiatement une" in result.pages[0].blocks[0].text
    assert "ressen-" not in result.pages[0].blocks[0].text


def test_line_break_merge_joins_sentence_fragments():
    blocks = [
        _block(14, 0, "vous ressentez immédiatement une", y0=136.8, y1=148.9, x0=123.0),
        _block(14, 1, "aura de terreur en", x0=134.0, y0=148.2, y1=160.3),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 1
    assert result.pages[0].blocks[0].text == (
        "vous ressentez immédiatement une aura de terreur en"
    )


def test_wrap_around_merge_joins_illustration_continuation():
    blocks = [
        _block(
            14,
            0,
            "aura de terreur en",
            x0=51.0,
            x1=218.8,
            y0=45.5,
            y1=160.3,
            italic=True,
        ),
        _block(
            14,
            1,
            "émaner. Proférant des menaces dans une langue.",
            x0=256.5,
            x1=424.3,
            y0=45.6,
            y1=103.3,
            italic=True,
        ),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 1
    assert len(result.pages[0].blocks) == 1
    assert result.pages[0].blocks[0].text == (
        "aura de terreur en émaner. Proférant des menaces dans une langue."
    )


def test_does_not_merge_after_strong_punctuation():
    blocks = [
        _block(14, 0, "les renforts.", y0=160.0, y1=170.0),
        _block(14, 1, "ensuite la scène continue.", y0=172.0, y1=182.0),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 0
    assert len(result.pages[0].blocks) == 2


def test_chains_multiple_merges_on_page_14_fragment():
    blocks = [
        _block(
            14,
            0,
            "La créature se retourne vers vous et vous ressen‑",
            y0=45.5,
            y1=137.5,
            italic=True,
        ),
        _block(14, 1, "tez immédiatement une", x0=123.0, y0=136.8, y1=148.9, italic=True),
        _block(14, 2, "aura de terreur en", x0=134.0, y0=148.2, y1=160.3, italic=True),
        _block(
            14,
            3,
            "émaner. Proférant des menaces.",
            x0=256.5,
            x1=424.3,
            y0=45.6,
            y1=103.3,
            italic=True,
        ),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 3
    assert len(result.pages[0].blocks) == 1
    assert "ressentez immédiatement une aura de terreur en émaner." in result.pages[0].blocks[0].text


def test_wrap_around_merge_page_15_stat_block():
    blocks = [
        _block(
            15,
            0,
            "PASSAGE DANS LA PIERRE :\nDeux fois par jour, la momie peut se déplacer dans toutes les",
            x0=51.0,
            x1=213.8,
            y0=512.0,
            y1=559.8,
            bold=True,
        ),
        _block(
            15,
            1,
            "directions. Elle peut emmener une personne avec elle grâce à ce pouvoir.",
            x0=260.8,
            x1=426.3,
            y0=45.7,
            y1=70.2,
        ),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 1
    assert len(result.pages[0].blocks) == 1
    assert "dans toutes les directions." in result.pages[0].blocks[0].text


def test_does_not_merge_cross_column_unrelated():
    blocks = [
        _block(
            14,
            0,
            "Les renforts arrivent enfin.",
            x0=51.0,
            x1=218.8,
            y0=500.0,
            y1=560.0,
        ),
        _block(
            14,
            1,
            "ensuite la scène continue.",
            x0=256.5,
            x1=424.3,
            y0=45.6,
            y1=103.3,
        ),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 0
    assert len(result.pages[0].blocks) == 2


def test_hyphenation_merge_without_strict_column_overlap():
    blocks = [
        _block(5, 0, "col-", x0=40.0, x1=90.0, y0=10.0, y1=20.0),
        _block(5, 1, "lection organisée", x0=200.0, x1=280.0, y0=10.0, y1=20.0),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    assert result.merged_block_count == 1
    assert result.pages[0].blocks[0].text == "collection organisée"


def test_drop_cap_merge_joins_letter_with_following_text():
    blocks = [
        _block(5, 0, "S", font_size=24, bold=True, x0=40.0, x1=55.0, y0=100.0, y1=140.0),
        _block(
            5,
            1,
            "i beaucoup ont oublié que les momies existent.",
            x0=60.0,
            x1=380.0,
            y0=110.0,
            y1=150.0,
        ),
    ]
    result = merge_drop_caps([_page(blocks)])

    assert result.merged_block_count == 1
    assert result.pages[0].blocks[0].text.startswith("Si beaucoup ont oublié")


def test_cross_page_merge_joins_wrap_around_fragment_on_next_page():
    page_six = _page(
        [
            _block(6, 0, "Ekhidna envoya ses enfants.", x0=248.0, x1=424.0, y0=91.0, y1=280.0),
            _block(6, 1, "Au", x0=248.0, x1=260.0, y0=285.0, y1=295.0),
        ]
    )
    page_six = LayoutPage(
        page_number=6,
        width=510.0,
        height=650.0,
        text=page_six.text,
        blocks=page_six.blocks,
    )
    page_seven = _page(
        [
            _block(
                7,
                0,
                "cours de cette surveillance que l'aigle poursuit un serpent.",
                x0=42.0,
                x1=227.0,
                y0=45.0,
                y1=103.0,
            ),
        ]
    )
    page_seven = LayoutPage(
        page_number=7,
        width=510.0,
        height=650.0,
        text=page_seven.text,
        blocks=page_seven.blocks,
    )
    result = merge_fragmented_blocks([page_six, page_seven])

    assert result.merged_block_count >= 1
    page_seven_blocks = result.pages[1].blocks
    assert page_seven_blocks[0].text.startswith("Au cours de cette surveillance")
    assert len(result.pages[0].blocks) == 1


def test_reindexes_blocks_after_merge():
    blocks = [
        _block(1, 0, "mot coupé‑", y0=10.0, y1=20.0),
        _block(1, 1, "ure complète.", y0=21.0, y1=31.0),
        _block(1, 2, "Nouveau paragraphe.", y0=60.0, y1=70.0),
    ]
    result = merge_fragmented_blocks([_page(blocks)])

    merged_blocks = result.pages[0].blocks
    assert [block.block_index for block in merged_blocks] == [0, 1]
    assert merged_blocks[0].text == "mot coupéure complète."
    assert merged_blocks[1].text == "Nouveau paragraphe."
