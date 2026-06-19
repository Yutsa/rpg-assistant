"""Synthetic PDF fixtures for ingestion pipeline tests."""

from __future__ import annotations

from pathlib import Path

import pymupdf


def build_multicolumn_nested_headings_pdf(path: Path) -> None:
    """Two-column page with nested headings and a second chapter page."""
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)

    page.insert_text((50, 80), "PARTIE I", fontsize=18)
    page.insert_text((50, 120), "EN QUELQUES MOTS", fontsize=14)
    page.insert_text((50, 150), "Résumé introductif dans la colonne gauche.", fontsize=11)
    page.insert_text((50, 190), "1.1 Sous-section", fontsize=13)
    page.insert_text(
        (50, 220),
        "Corps de la sous-section avec détails narratifs.",
        fontsize=11,
    )
    page.insert_text((320, 80), "Colonne droite indépendante.", fontsize=11)
    page.insert_text((320, 110), "Suite du texte à droite.", fontsize=11)

    page2 = document.new_page(width=612, height=792)
    page2.insert_text((50, 80), "PARTIE II", fontsize=18)
    page2.insert_text((50, 120), "Chapitre suivant sur page deux.", fontsize=11)

    document.save(path)
    document.close()


def build_dense_text_pdf(path: Path, *, chars_per_page: int = 3000) -> None:
    """Build a single-page PDF with enough text to pass coverage threshold."""
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    paragraph = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    )
    repeats = max(1, chars_per_page // len(paragraph))
    body = (paragraph * repeats)[:chars_per_page]
    page.insert_text((72, 72), f"Document\n\n{body}", fontsize=11)
    document.save(path)
    document.close()
