"""Benchmark helpers for the legacy extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.chunking import build_chunks, chunk_uniqueness_stats
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.sections import detect_sections, refine_section_page_ends
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_core.storage.ids import page_block_id


@dataclass
class PipelineScore:
    blocks: int
    sections: int
    chunks: int
    missing_blocks: int
    duplicate_chunks: int
    section_titles: list[str]
    quality_points: int = 0
    quality_notes: list[str] | None = None

    @property
    def coverage_ok(self) -> bool:
        return self.missing_blocks == 0 and self.duplicate_chunks == 0


def _postprocess_pages(
    pages: list[LayoutPage],
    *,
    game_system: str,
) -> tuple[list[LayoutPage], object]:
    profile = resolve_profile(game_system, pages)
    pages = filter_watermark_blocks(pages).pages
    pages = merge_fragmented_blocks(pages, profile=profile).pages
    pages = merge_drop_caps(pages).pages
    stat_result = annotate_stat_blocks(pages, profile)
    return stat_result.pages, stat_result


def run_legacy_pipeline(
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    game_system: str = "cof2",
) -> tuple[PipelineScore, list, list]:
    pages, stat_result = _postprocess_pages(pages, game_system=game_system)
    profile = resolve_profile(game_system, pages)
    section_result = detect_sections(
        pages,
        campaign_id=campaign_id,
        document_id=document_id,
        profile=profile,
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id=campaign_id,
        document_id=document_id,
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
        stat_spans=stat_result.spans,
        profile=profile,
    )
    refine_section_page_ends(section_result.sections, chunks)
    score = _score_result(
        pages,
        section_result.sections,
        chunks,
        document_id=document_id,
        heading_anchors=section_result.heading_anchors,
    )
    return score, chunks, section_result.sections


def _score_result(
    pages: list[LayoutPage],
    sections,
    chunks,
    *,
    document_id: str,
    heading_anchors: list[tuple[int, int]],
) -> PipelineScore:
    heading_positions = set(heading_anchors)
    content_ids = {
        page_block_id(document_id, page.page_number, block.block_index)
        for page in pages
        for block in page.blocks
        if (page.page_number, block.block_index) not in heading_positions
    }
    referenced = {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }
    uniqueness = chunk_uniqueness_stats(chunks)
    return PipelineScore(
        blocks=sum(len(page.blocks) for page in pages),
        sections=len(sections),
        chunks=len(chunks),
        missing_blocks=len(content_ids - referenced),
        duplicate_chunks=int(uniqueness["duplicate_chunk_count"]),
        section_titles=[section.title for section in sections],
    )


def score_synthetic_rpg(
    score: PipelineScore,
    chunks,
    *,
    sections,
) -> PipelineScore:
    notes: list[str] = []
    points = 0
    titles = [title.casefold() for title in score.section_titles]
    if any("chroniques" in title for title in titles):
        points += 1
    else:
        notes.append("missing chroniques section")
    if any("crypte" in title for title in titles):
        points += 1
    else:
        notes.append("missing crypte section")
    if not any("momie ancienne" == title.strip() for title in titles):
        points += 1
    else:
        notes.append("spurious momie section title")
    encadre_chunk = next(
        (
            chunk
            for chunk in chunks
            if chunk.text.strip() == "Encadre MJ"
        ),
        None,
    )
    if encadre_chunk is not None:
        points += 2
        notes.append("encadre isolated")
    crypte = next((s for s in sections if "crypte" in s.title.casefold()), None)
    if crypte is not None:
        crypte_text = " ".join(
            chunk.text for chunk in chunks if chunk.section_id == crypte.id
        )
        if "embuscade" in crypte_text.casefold() and "torche" in crypte_text.casefold():
            points += 1
        else:
            notes.append("crypte chunk missing list/sidebar")
    return PipelineScore(
        blocks=score.blocks,
        sections=score.sections,
        chunks=score.chunks,
        missing_blocks=score.missing_blocks,
        duplicate_chunks=score.duplicate_chunks,
        section_titles=score.section_titles,
        quality_points=points,
        quality_notes=notes,
    )


def score_page8_layout(score: PipelineScore, chunks, *, sections) -> PipelineScore:
    notes: list[str] = []
    points = 0
    if score.sections >= 4:
        points += 2
    else:
        notes.append("expected >=4 sections")
    mj = next((section for section in sections if "MJ" in section.title), None)
    act = next(
        (section for section in sections if "acteurs" in section.title.casefold()),
        None,
    )
    if mj is not None:
        mj_text = " ".join(chunk.text for chunk in chunks if chunk.section_id == mj.id)
        if "Il est temps pour les PJ" in mj_text:
            points += 2
        else:
            notes.append("PJ text missing from MJ section")
        if "Kalian" not in mj_text:
            points += 1
        else:
            notes.append("Kalian wrongly in MJ section")
    if act is not None:
        act_text = " ".join(chunk.text for chunk in chunks if chunk.section_id == act.id)
        if "Kalian" in act_text:
            points += 1
        else:
            notes.append("Kalian missing from acteurs")
        if "Il est temps pour les PJ" not in act_text:
            points += 1
        else:
            notes.append("PJ text wrongly in acteurs")
    return PipelineScore(
        blocks=score.blocks,
        sections=score.sections,
        chunks=score.chunks,
        missing_blocks=score.missing_blocks,
        duplicate_chunks=score.duplicate_chunks,
        section_titles=score.section_titles,
        quality_points=points,
        quality_notes=notes,
    )
