from rpg_core.text.reflow import reflow_chunk_text


def test_joins_hyphenated_line_breaks() -> None:
    text = "Un long mot-\nvant la suite."
    assert reflow_chunk_text(text) == "Un long motvant la suite."


def test_preserves_paragraph_breaks() -> None:
    text = "Premier paragraphe\nsur deux lignes.\n\nDeuxième paragraphe."
    assert (
        reflow_chunk_text(text)
        == "Premier paragraphe sur deux lignes.\n\nDeuxième paragraphe."
    )


def test_normalizes_non_breaking_spaces() -> None:
    text = "Mot\u00a0suivant\u202fici."
    assert reflow_chunk_text(text) == "Mot suivant ici."


def test_idempotent() -> None:
    text = "Ligne un\nligne deux\n\nParagraphe\u00a0deux."
    once = reflow_chunk_text(text)
    assert reflow_chunk_text(once) == once


def test_soft_hyphen_at_line_end() -> None:
    text = "exem\u00ad\nple"
    assert reflow_chunk_text(text) == "exemple"
