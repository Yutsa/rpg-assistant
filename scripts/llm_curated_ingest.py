#!/usr/bin/env python3
"""Run LLM-curated ingestion for COF2 benchmark PDFs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from rpg_ingest.llm_curated.ingest import ingest_llm_curated_pdf
from tests.fixtures.real_pdf_benchmark import FAELYS_SPEC, MONDANITES_SPEC, resolve_real_pdf_path


def main() -> int:
    specs = [MONDANITES_SPEC, FAELYS_SPEC]
    for spec in specs:
        pdf = resolve_real_pdf_path(spec)
        if pdf is None:
            env = os.environ.get(spec.env_var, "")
            print(f"SKIP {spec.benchmark_id}: set {spec.env_var} ({env!r})")
            continue
        result = ingest_llm_curated_pdf(
            pdf,
            benchmark_id=spec.benchmark_id,
            campaign_id=spec.campaign_id,
            game_system=spec.game_system,
        )
        print(f"OK {spec.benchmark_id}")
        print(f"  document_id={result.document_id}")
        print(f"  run_id={result.ingestion_run_id}")
        print(f"  notes={result.curation_notes}")
        print(f"  stats={result.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
