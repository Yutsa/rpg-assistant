"""Editorial curation rules derived from visual PDF review (agent pass).

Each function documents a decision made after reading the COF2 layout:
- column boxes (EN QUELQUES MOTS / FICHE TECHNIQUE)
- Partie I–IV hierarchy
- credits vs narrative separation (Faelys p4–5)
- drame vs investigations split (Momie p9–10)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rpg_core.models.raw import ChunkRecord, SectionRecord

_BANNER_DUP_RE = re.compile(
    r"^(?P<a>.+?)\s+\1$",
    re.IGNORECASE,
)


@dataclass
class CuratedPipeline:
    sections: list[SectionRecord]
    chunks: list[ChunkRecord]
    notes: list[str]


def _normalize_title(title: str) -> str:
    text = title.replace("\u2019", "'").replace("\u202f", " ")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).strip()


def _deduplicate_banner_titles(sections: list[SectionRecord], notes: list[str]) -> None:
    """Momie p1: sidebar banner duplicated in heading extraction."""
    for section in sections:
        match = _BANNER_DUP_RE.match(_normalize_title(section.title))
        if match:
            section.title = match.group("a").strip()
            notes.append(f"dedup banner: {section.id}")


def _remove_spurious_introductions(
    sections: list[SectionRecord],
    chunks: list[ChunkRecord],
    *,
    benchmark_id: str,
    notes: list[str],
) -> None:
    """Drop false-positive Introduction sections (pymupdf4llm regression on Momie p8)."""
    if benchmark_id != "mondanites":
        return
    drop_ids: set[str] = set()
    for section in sections:
        if section.title != "Introduction":
            continue
        # Page 8 false Introduction (pymupdf4llm); p16 Partie IV layout artefact.
        if section.page_start in {8, 16}:
            drop_ids.add(section.id)
            notes.append(f"drop spurious Introduction p{section.page_start}")
    if not drop_ids:
        return
    remaining = [s for s in sections if s.id not in drop_ids]
    # Re-parent chunks that pointed at dropped sections to nearest Partie section.
    for chunk in chunks:
        if chunk.section_id in drop_ids:
            partie = next(
                (
                    s
                    for s in remaining
                    if s.page_start <= chunk.page_start <= s.page_end
                    and "PARTIE" in s.title.upper()
                ),
                None,
            )
            chunk.section_id = partie.id if partie else None
    sections[:] = remaining


def _fix_en_quelques_mots_hierarchy(
    sections: list[SectionRecord],
    notes: list[str],
) -> None:
    """Momie p5: synopsis box must not be child of Partie I (audit + visual review)."""
    en_quelques = next(
        (s for s in sections if _normalize_title(s.title).upper() == "EN QUELQUES MOTS"),
        None,
    )
    if en_quelques is None:
        return
    if en_quelques.parent_section_id is not None:
        en_quelques.parent_section_id = None
        en_quelques.level = 1
        notes.append("EN QUELQUES MOTS promoted to root (sidebar box)")


def _normalize_multiline_titles(sections: list[SectionRecord], notes: list[str]) -> None:
    """Collapse newline-split headings from column layout (e.g. Drame\\nau cabinet)."""
    for section in sections:
        if "\n" not in section.title:
            continue
        collapsed = re.sub(r"\s+", " ", section.title.replace("\n", " ")).strip()
        if collapsed != section.title:
            section.title = collapsed
            notes.append(f"collapse title: {collapsed[:50]}")


def _ensure_grandes_lignes_under_partie_i(
    sections: list[SectionRecord],
    notes: list[str],
) -> None:
    """Momie p5: 'Les grandes lignes' belongs under Partie I (visual two-column layout)."""
    partie_i = next(
        (s for s in sections if re.search(r"partie\s+i\b", _normalize_title(s.title), re.I)),
        None,
    )
    grandes = next(
        (s for s in sections if "grandes lignes" in _normalize_title(s.title).casefold()),
        None,
    )
    if partie_i and grandes and grandes.parent_section_id != partie_i.id:
        grandes.parent_section_id = partie_i.id
        grandes.level = 2
        notes.append("Les grandes lignes under Partie I")


def curate_pipeline_result(
    *,
    benchmark_id: str,
    sections: list[SectionRecord],
    chunks: list[ChunkRecord],
) -> CuratedPipeline:
    """Apply editorial fixes after mechanical legacy extraction."""
    notes: list[str] = []
    section_list = [s.model_copy(deep=True) for s in sections]
    chunk_list = [c.model_copy(deep=True) for c in chunks]

    _deduplicate_banner_titles(section_list, notes)
    _normalize_multiline_titles(section_list, notes)
    _remove_spurious_introductions(
        section_list, chunk_list, benchmark_id=benchmark_id, notes=notes
    )
    if benchmark_id == "mondanites":
        _fix_en_quelques_mots_hierarchy(section_list, notes)
        _ensure_grandes_lignes_under_partie_i(section_list, notes)

    return CuratedPipeline(sections=section_list, chunks=chunk_list, notes=notes)
