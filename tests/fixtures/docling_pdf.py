"""Synthetic PDF fixtures for Docling integration tests."""

from __future__ import annotations

from pathlib import Path

import pymupdf


def build_docling_synthetic_pdf(path: Path) -> Path:
    """Create a synthetic RPG-style PDF for Docling pipeline validation.

    Layout:
    - Page 1: two columns with H1, H2, list items, sidebar encadré
    - Page 2: COF2-style stat block
    """
    doc = pymupdf.open()
    page1 = doc.new_page(width=612, height=792)

    # Left column — main narrative
    page1.insert_text((72, 72), "LES CHRONIQUES OUBLIEES", fontsize=18)
    page1.insert_text((72, 110), "Chapitre 1 — La Crypte", fontsize=14)
    page1.insert_text(
        (72, 145),
        "Les aventuriers penetrent dans la crypte ancienne.",
        fontsize=11,
    )
    page1.insert_text((72, 175), "- Torche allumee", fontsize=11)
    page1.insert_text((72, 195), "- Porte verrouillee", fontsize=11)
    page1.insert_text((72, 215), "- Passage secret", fontsize=11)

    # Right column — encadré / sidebar
    page1.insert_text((330, 72), "Encadre MJ", fontsize=12)
    page1.insert_text(
        (330, 100),
        "Si les PJ echouent, declencher une embuscade.",
        fontsize=10,
    )

    # Page 2 — stat block (COF2)
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((72, 72), "MOMIE ANCIENNE", fontsize=12)
    page2.insert_text(
        (72, 95),
        "MOMIE ANCIENNE | NC 5",
        fontsize=12,
    )
    page2.insert_text(
        (72, 120),
        "AGI +0 | FOR +3 | CON +2 | INT -1 | PER +0 | CHA +0",
        fontsize=10,
    )
    page2.insert_text(
        (72, 150),
        "POURRISSEMENT :\nLa momie emet une odeur nauseabonde.",
        fontsize=10,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path
