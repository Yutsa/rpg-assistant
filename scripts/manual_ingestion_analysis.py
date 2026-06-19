#!/usr/bin/env python3
"""Quick manual inspection of legacy vs docling ingestion on real PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.real_pdf_benchmark import (
    BENCHMARK_CHECKS,
    FAELYS_SPEC,
    MONDANITES_SPEC,
    PROVIDERS,
    RealPdfSpec,
    resolve_real_pdf_path,
    run_real_pdf_benchmark,
)


def _run_checks(spec: RealPdfSpec, pdf_path: Path) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    for provider in PROVIDERS:
        run = run_real_pdf_benchmark(spec, pdf_path, provider=provider)
        provider_results: dict[str, str] = {
            "chunks": str(len(run.chunks)),
            "sections": str(len(run.sections)),
            "missing_blocks": str(run.missing_blocks),
            "duplicate_chunks": str(run.duplicate_chunks),
        }
        checks = BENCHMARK_CHECKS[spec.benchmark_id]
        for check in checks:
            try:
                check.fn(run)
                provider_results[check.check_id] = "PASS"
            except AssertionError as exc:
                provider_results[check.check_id] = f"FAIL: {exc}"
        results[provider] = provider_results
    return results


def main() -> None:
    all_results: dict[str, dict[str, dict[str, str]]] = {}
    for spec in (MONDANITES_SPEC, FAELYS_SPEC):
        path = resolve_real_pdf_path(spec)
        if path is None:
            print(f"SKIP {spec.benchmark_id}: PDF not found")
            continue
        print(f"\n=== {spec.benchmark_id} ({path.name}) ===")
        results = _run_checks(spec, path)
        all_results[spec.benchmark_id] = results
        for provider, checks in results.items():
            print(f"\n--- {provider} ---")
            print(
                f"  chunks={checks['chunks']} sections={checks['sections']} "
                f"missing={checks['missing_blocks']} dup={checks['duplicate_chunks']}"
            )
            for check_id, status in checks.items():
                if check_id in ("chunks", "sections", "missing_blocks", "duplicate_chunks"):
                    continue
                mark = "✓" if status == "PASS" else "✗"
                print(f"  {mark} {check_id}: {status}")

    out = Path("/workspace/data/manual_analysis_results.json")
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
