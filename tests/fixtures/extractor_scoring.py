"""Quality scoring for legacy vs pymupdf4llm extractor comparisons."""

from __future__ import annotations

from tests.fixtures.pipeline import PipelineResult


def score_page8_layout(result: PipelineResult) -> int:
    """Higher is better. Max 5 points."""
    by_title = {section.title: section.id for section in result.sections}
    titles = set(by_title)

    def joined(title: str) -> str:
        section_id = by_title.get(title)
        if section_id is None:
            return ""
        return " ".join(
            chunk.text for chunk in result.chunks if chunk.section_id == section_id
        )

    partie_titles = [
        title for title in titles if title.startswith("PARTIE I")
    ]
    partie_text = " ".join(joined(title) for title in partie_titles)
    mj_text = joined("L'histoire pour le MJ")
    acteurs_text = joined("Les différents acteurs")

    points = 0
    if "Il est temps pour les PJ" in mj_text or "Il est temps pour les PJ" in partie_text:
        points += 1
    if "Kalian" in acteurs_text and "Hector" in acteurs_text:
        points += 1
    if "Il est temps pour les PJ" not in acteurs_text:
        points += 1
    if "Taless Rhann" in mj_text:
        points += 1
    if "Introduction" not in titles:
        points += 1
    return points


def score_momie_synopsis(result: PipelineResult) -> int:
    """Higher is better. Max 4 points."""
    points = 0
    titles = [section.title for section in result.sections]
    all_text = " ".join(chunk.text for chunk in result.chunks)

    if "Document" not in titles:
        points += 1
    if any("MALÉDICTION" in title for title in titles):
        points += 1
    if "malédiction pèse sur la région" in all_text:
        points += 1
    if "Black Book" in all_text or "Tous droits réservés" in all_text:
        points += 1
    return points


def score_multicolumn(result: PipelineResult) -> int:
    """Higher is better. Max 4 points."""
    by_title = {section.title: section.id for section in result.sections}
    points = 0
    expected_titles = {
        "PARTIE I",
        "EN QUELQUES MOTS",
        "1.1 Sous-section",
        "PARTIE II",
    }
    if expected_titles.issubset(by_title):
        points += 1

    partie_id = by_title.get("PARTIE I")
    if partie_id:
        partie_text = " ".join(
            c.text for c in result.chunks if c.section_id == partie_id
        )
        if "Colonne droite indépendante." in partie_text:
            points += 1
        if "Résumé introductif" in partie_text:
            points += 1

    enqm_id = by_title.get("EN QUELQUES MOTS")
    if enqm_id:
        enqm_chunks = [c for c in result.chunks if c.section_id == enqm_id]
        if not enqm_chunks:
            points += 1

    if result.chunks and all(
        len(chunk.source_spans) > 0 for chunk in result.chunks
    ):
        points += 1
    return points
