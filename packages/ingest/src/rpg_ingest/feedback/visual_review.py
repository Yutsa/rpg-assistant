from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from rpg_core.models.raw import ChunkRecord, SectionRecord
from rpg_core.storage.repositories.raw import RawRepository


VISUAL_INGESTION_REVIEW_PROMPT = """# Visual ingestion review

Compare the rendered PDF page images with the extracted sections and chunks from the database.

## Checklist per sample

1. **Section title** — Is the section title visible on `page_start`? Does the heading level look correct?
2. **Chunk text** — Does each chunk's text match the visible content? Look for missing words, incorrect merges, wrong order, or duplicated text.
3. **Page boundaries** — Do `page_start` and `page_end` on each chunk cover the text that is actually visible?
4. **Section span** — Does `page_end` on the section match the visual structure (next heading or end of content)?
5. **Anomalies** — Ghost headings, column misreads, headers/footers included in body text, watermark remnants.

## Output format

For each sample, assign a verdict: `pass`, `minor_issues`, or `major_issues`.

Report issues as structured findings:

```json
{
  "findings": [
    {
      "section_id": "...",
      "chunk_id": "... or null",
      "page": 5,
      "severity": "minor|major",
      "issue": "short description",
      "suggestion": "optional fix hint"
    }
  ],
  "summary": "one paragraph overview"
}
```
"""


class VisualReviewError(Exception):
    pass


@dataclass
class SectionSample:
    section: SectionRecord
    chunks: list[ChunkRecord]
    pages_to_review: list[int]


@dataclass
class VisualReviewSample:
    seed: int | None
    samples: list[SectionSample] = field(default_factory=list)
    all_pages: list[int] = field(default_factory=list)
    pages_truncated: bool = False


def resolve_pdf_path(
    repo: RawRepository,
    document_id: str,
    pdf_path_override: str | Path | None = None,
) -> Path:
    if pdf_path_override:
        path = Path(pdf_path_override).resolve()
        if not path.is_file():
            raise VisualReviewError(f"PDF not found: {path}")
        return path

    run = repo.get_latest_raw_run(document_id)
    if run and run.stats.get("source_pdf_path"):
        path = Path(run.stats["source_pdf_path"]).resolve()
        if path.is_file():
            return path
        raise VisualReviewError(
            f"Stored source_pdf_path no longer exists: {path}. "
            "Re-import the PDF or pass pdf_path explicitly."
        )

    raise VisualReviewError(
        f"No source_pdf_path found for document {document_id}. "
        "Re-import the PDF or pass pdf_path explicitly."
    )


def _pages_for_sample(section: SectionRecord, chunks: list[ChunkRecord]) -> list[int]:
    pages: set[int] = {section.page_start}
    for chunk in chunks:
        for span in chunk.source_spans:
            pages.add(span.page)
        pages.add(chunk.page_start)
        pages.add(chunk.page_end)
    return sorted(pages)


def build_visual_review_sample(
    sections: list[SectionRecord],
    chunks_by_section: dict[str, list[ChunkRecord]],
    *,
    section_count: int = 3,
    chunks_per_section: int = 2,
    seed: int | None = None,
    max_pages: int = 15,
    sections_preselected: bool = False,
) -> VisualReviewSample:
    rng = random.Random(seed)
    if sections_preselected:
        picked_sections = sections
    else:
        eligible = [
            section
            for section in sections
            if chunks_by_section.get(section.id)
        ]
        if not eligible:
            raise VisualReviewError("No sections with chunks available for visual review.")

        pick_count = min(section_count, len(eligible))
        picked_sections = rng.sample(eligible, pick_count)

    samples: list[SectionSample] = []
    all_pages: set[int] = set()

    for section in picked_sections:
        section_chunks = list(chunks_by_section.get(section.id, []))
        chunk_pick_count = min(chunks_per_section, len(section_chunks))
        picked_chunks = (
            rng.sample(section_chunks, chunk_pick_count)
            if chunk_pick_count < len(section_chunks)
            else section_chunks
        )
        pages = _pages_for_sample(section, picked_chunks)
        all_pages.update(pages)
        samples.append(
            SectionSample(section=section, chunks=picked_chunks, pages_to_review=pages)
        )

    sorted_pages = sorted(all_pages)
    pages_truncated = len(sorted_pages) > max_pages
    if pages_truncated:
        sorted_pages = sorted_pages[:max_pages]

    return VisualReviewSample(
        seed=seed,
        samples=samples,
        all_pages=sorted_pages,
        pages_truncated=pages_truncated,
    )


def _chunk_payload(chunk: ChunkRecord) -> dict:
    return {
        "id": chunk.id,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "text": chunk.text,
        "source_spans": [span.model_dump() for span in chunk.source_spans],
        "chunk_type_hint": chunk.chunk_type_hint,
    }


def build_visual_review_payload(
    *,
    document_id: str,
    pdf_path: Path,
    sample: VisualReviewSample,
    page_images: dict[int, Path],
) -> dict:
    return {
        "document_id": document_id,
        "pdf_path": str(pdf_path),
        "seed": sample.seed,
        "pages_truncated": sample.pages_truncated,
        "samples": [
            {
                "section": {
                    "id": item.section.id,
                    "title": item.section.title,
                    "level": item.section.level,
                    "page_start": item.section.page_start,
                    "page_end": item.section.page_end,
                },
                "chunks": [_chunk_payload(chunk) for chunk in item.chunks],
                "pages_to_review": item.pages_to_review,
            }
            for item in sample.samples
        ],
        "page_images": [
            {
                "page_number": page_number,
                "image_path": str(image_path.resolve()),
            }
            for page_number, image_path in sorted(page_images.items())
        ],
        "review_instructions_uri": "ingestion://prompts/visual_ingestion_review",
    }


def prepare_visual_ingestion_review(
    repo: RawRepository,
    document_id: str,
    *,
    pdf_path: str | Path | None = None,
    section_count: int = 3,
    chunks_per_section: int = 2,
    seed: int | None = None,
    dpi: int = 150,
    max_pages: int = 15,
) -> dict:
    from rpg_ingest.raw.rendering import render_pdf_pages

    resolved_pdf = resolve_pdf_path(repo, document_id, pdf_path)
    sections = repo.list_sections(document_id)
    if not sections:
        raise VisualReviewError(f"No sections found for document {document_id}.")

    chunked_ids = repo.section_ids_with_chunks(document_id)
    eligible = [section for section in sections if section.id in chunked_ids]
    if not eligible:
        raise VisualReviewError("No sections with chunks available for visual review.")

    rng = random.Random(seed)
    picked_sections = rng.sample(eligible, min(section_count, len(eligible)))
    sample = build_visual_review_sample(
        picked_sections,
        repo.list_chunks_for_sections(document_id, [s.id for s in picked_sections]),
        section_count=len(picked_sections),
        chunks_per_section=chunks_per_section,
        seed=seed,
        max_pages=max_pages,
        sections_preselected=True,
    )

    page_images = render_pdf_pages(
        resolved_pdf,
        sample.all_pages,
        document_id=document_id,
        dpi=dpi,
    )

    return build_visual_review_payload(
        document_id=document_id,
        pdf_path=resolved_pdf,
        sample=sample,
        page_images=page_images,
    )
