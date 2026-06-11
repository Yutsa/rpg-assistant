from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.models.raw import BBox


def _block(
    page: int,
    index: int,
    text: str,
    font_size: float,
    bold: bool = False,
    *,
    x0: float = 0,
    y0: float = 0,
    x1: float = 100,
    y1: float = 20,
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


def test_detect_sections_finds_chapter_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Chapter 1\nIntro body text here.",
            blocks=[
                _block(1, 0, "Chapter 1", 18, bold=True),
                _block(1, 1, "Intro body text here.", 11),
            ],
        ),
        LayoutPage(
            page_number=2,
            width=612,
            height=792,
            text="Chapter 2\nMore content.",
            blocks=[
                _block(2, 0, "Chapter 2", 18, bold=True),
                _block(2, 1, "More content.", 11),
            ],
        ),
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert len(result.sections) == 2
    assert result.sections[0].title == "Chapter 1"
    assert result.sections[0].level == 1
    assert result.sections[1].title == "Chapter 2"
    assert result.heading_anchors == [(1, 0), (2, 0)]


def test_detect_sections_fallback_when_no_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Plain paragraph without headings.",
            blocks=[_block(1, 0, "Plain paragraph without headings.", 11)],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert len(result.sections) == 1
    assert result.sections[0].title == "Document"
    assert result.heading_anchors == []


def test_detect_sections_rejects_single_character_drop_cap_heading():
    pages = [
        LayoutPage(
            page_number=5,
            width=612,
            height=792,
            text="S\ni beaucoup ont oublié.",
            blocks=[
                _block(5, 0, "S", 24, bold=True),
                _block(5, 1, "i beaucoup ont oublié.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    titles = [section.title for section in result.sections]
    assert "S" not in titles


def test_detect_sections_keeps_three_character_bold_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="Fin\nNotes here.",
            blocks=[
                _block(1, 0, "Fin", 16, bold=True),
                _block(1, 1, "Notes here.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert [section.title for section in result.sections] == ["Fin"]


def test_detect_sections_rejects_decorative_spread_title():
    pages = [
        LayoutPage(
            page_number=5,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(5, 0, "MONDANITÉS", 42, bold=True, x0=104, y0=36, x1=384, y1=88),
                _block(5, 1, "ET MOMIE", 42, bold=True, x0=139, y0=82, x1=333, y1=134),
                _block(5, 2, "EN QUELQUES MOTS", 11, bold=True, x0=78, y0=219, x1=190, y1=232),
                _block(5, 3, "Résumé.", 9, x0=48, y0=237, x1=222, y1=300),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    titles = [section.title for section in result.sections]
    assert "MONDANITÉS" not in titles
    assert "ET MOMIE" not in titles
    assert "EN QUELQUES MOTS" in titles


def test_detect_sections_nests_subordinates_under_chapter():
    pages = [
        LayoutPage(
            page_number=5,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(
                    5,
                    0,
                    "Les grandes lignes",
                    13,
                    bold=True,
                    x0=248,
                    y0=389,
                    x1=368,
                    y1=404,
                ),
                _block(
                    5,
                    1,
                    "PARTIE I :\nL'HISTOIRE EN UN COUP D'ŒIL",
                    14,
                    bold=True,
                    x0=43,
                    y0=459,
                    x1=225,
                    y1=489,
                ),
                _block(5, 2, "Corps de la partie.", 9, x0=43, y0=493, x1=227, y1=551),
                _block(5, 3, "Les PJ sont invités.", 9, x0=248, y0=406, x1=433, y1=567),
            ],
        ),
        LayoutPage(
            page_number=7,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(
                    7,
                    0,
                    "L'histoire pour le MJ",
                    13,
                    bold=True,
                    x0=43,
                    y0=123,
                    x1=177,
                    y1=138,
                ),
                _block(7, 1, "Secrets pour le MJ.", 9, x0=43, y0=140, x1=227, y1=357),
            ],
        ),
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    partie = next(s for s in result.sections if s.title.startswith("PARTIE I"))
    grandes_lignes = next(s for s in result.sections if s.title == "Les grandes lignes")
    histoire_mj = next(s for s in result.sections if s.title == "L'histoire pour le MJ")
    assert partie.parent_section_id is None
    assert grandes_lignes.parent_section_id == partie.id
    assert histoire_mj.parent_section_id == partie.id


def test_detect_sections_finds_title_case_heading():
    pages = [
        LayoutPage(
            page_number=5,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(5, 0, "Les grandes lignes", 13, bold=True),
                _block(5, 1, "Les PJ sont invités.", 9),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert [section.title for section in result.sections] == ["Les grandes lignes"]


def test_detect_sections_no_false_preamble_when_chapter_in_parallel_column():
    """Left-column body above a right-column PARTIE must not spawn Introduction."""
    pages = [
        LayoutPage(
            page_number=8,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(
                    8,
                    0,
                    "Il est temps pour les PJ de découvrir la vérité.",
                    9.5,
                    x0=43,
                    y0=46,
                    x1=227,
                    y1=90,
                ),
                _block(
                    8,
                    1,
                    "Les différents acteurs",
                    13,
                    bold=True,
                    x0=43,
                    y0=250,
                    x1=200,
                    y1=265,
                ),
                _block(
                    8,
                    2,
                    "• Kalian : marchand ambitieux.",
                    9.5,
                    x0=43,
                    y0=270,
                    x1=227,
                    y1=300,
                ),
                _block(
                    8,
                    3,
                    "• Hector : garde du corps.",
                    9.5,
                    x0=248,
                    y0=46,
                    x1=433,
                    y1=76,
                ),
                _block(
                    8,
                    4,
                    "• Elsirianne : érudite de Piémont.",
                    9.5,
                    x0=248,
                    y0=80,
                    x1=433,
                    y1=110,
                ),
                _block(
                    8,
                    5,
                    "PARTIE II :\nL'ENQUÊTE",
                    14,
                    bold=True,
                    x0=248,
                    y0=459,
                    x1=400,
                    y1=489,
                ),
                _block(
                    8,
                    6,
                    "Corps de la partie II.",
                    9.5,
                    x0=248,
                    y0=493,
                    x1=433,
                    y1=551,
                ),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    titles = [section.title for section in result.sections]
    assert "Introduction" not in titles
    assert "Les différents acteurs" in titles
    assert any(title.startswith("PARTIE II") for title in titles)


def test_detect_sections_keeps_same_page_subordinates_under_first_chapter():
    """Subordinates between two chapters on one page stay under the earlier chapter."""
    pages = [
        LayoutPage(
            page_number=5,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(
                    5,
                    0,
                    "PARTIE I :\nL'HISTOIRE",
                    14,
                    bold=True,
                    x0=43,
                    y0=100,
                    x1=225,
                    y1=130,
                ),
                _block(
                    5,
                    1,
                    "Les grandes lignes",
                    15,
                    bold=True,
                    x0=248,
                    y0=150,
                    x1=368,
                    y1=165,
                ),
                _block(5, 2, "Corps partie I.", 9, x0=43, y0=170, x1=227, y1=220),
                _block(
                    5,
                    3,
                    "PARTIE II :\nL'ENQUÊTE",
                    14,
                    bold=True,
                    x0=248,
                    y0=400,
                    x1=400,
                    y1=430,
                ),
                _block(5, 4, "Corps partie II.", 9, x0=248, y0=440, x1=433, y1=500),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    partie_i = next(s for s in result.sections if s.title.startswith("PARTIE I"))
    partie_ii = next(s for s in result.sections if s.title.startswith("PARTIE II"))
    grandes_lignes = next(s for s in result.sections if s.title == "Les grandes lignes")
    assert grandes_lignes.parent_section_id == partie_i.id
    assert grandes_lignes.parent_section_id != partie_ii.id


def test_detect_sections_nests_numbered_heading_under_pre_chapter_title_case():
    pages = [
        LayoutPage(
            page_number=16,
            width=510,
            height=650,
            text="",
            blocks=[
                _block(
                    16,
                    0,
                    "Les abattoirs",
                    15,
                    bold=True,
                    x0=43,
                    y0=200,
                    x1=150,
                    y1=215,
                ),
                _block(
                    16,
                    1,
                    "1 - Cave de l'abattoir",
                    13,
                    bold=True,
                    x0=43,
                    y0=230,
                    x1=200,
                    y1=245,
                ),
                _block(16, 2, "Description de la cave.", 9, x0=43, y0=250, x1=227, y1=300),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    abattoirs = next(s for s in result.sections if s.title == "Les abattoirs")
    cave = next(s for s in result.sections if s.title.startswith("1"))
    assert abattoirs.parent_section_id is None
    assert cave.parent_section_id == abattoirs.id


def test_detect_sections_rejects_two_character_bold_headings():
    pages = [
        LayoutPage(
            page_number=1,
            width=612,
            height=792,
            text="GM\nNotes here.",
            blocks=[
                _block(1, 0, "GM", 16, bold=True),
                _block(1, 1, "Notes here.", 11),
            ],
        )
    ]
    result = detect_sections(pages, campaign_id="camp_test", document_id="doc_test")
    assert result.sections[0].title == "Document"
