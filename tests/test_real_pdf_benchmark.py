"""Real PDF ingestion benchmarks with statically encoded expectations.

Requires proprietary COF2 PDFs outside the repository. Configure paths via:

- ``RPG_PDF_MOMIE`` → Mondanités et Momie
- ``RPG_PDF_FAELYS`` → Le Dernier Faelys

Run only these tests::

    uv run python -m pytest tests/test_real_pdf_benchmark.py -m real_pdf -q

Run a single document/provider::

    uv run python -m pytest tests/test_real_pdf_benchmark.py -k "mondanites and docling" -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.real_pdf_benchmark import (
    BENCHMARK_CHECKS,
    PROVIDERS,
    REAL_PDF_SPECS,
    BenchmarkCheck,
    RealPdfSpec,
    resolve_real_pdf_path,
    run_benchmark_checks,
    run_real_pdf_benchmark,
    skip_reason,
)

_CHECK_PARAMS = [
    pytest.param(
        spec.benchmark_id,
        check,
        provider,
        id=f"{spec.benchmark_id}-{check.check_id}-{provider}",
    )
    for spec in REAL_PDF_SPECS
    for check in BENCHMARK_CHECKS[spec.benchmark_id]
    for provider in PROVIDERS
]


def _spec_by_id(benchmark_id: str) -> RealPdfSpec:
    for spec in REAL_PDF_SPECS:
        if spec.benchmark_id == benchmark_id:
            return spec
    raise KeyError(benchmark_id)


@pytest.fixture(scope="module")
def real_pdf_paths() -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for spec in REAL_PDF_SPECS:
        path = resolve_real_pdf_path(spec)
        if path is not None:
            resolved[spec.benchmark_id] = path
    return resolved


@pytest.mark.real_pdf
@pytest.mark.parametrize("benchmark_id", [spec.benchmark_id for spec in REAL_PDF_SPECS])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_real_pdf_benchmark_suite(
    benchmark_id: str,
    provider: str,
    real_pdf_paths: dict[str, Path],
) -> None:
    """Full benchmark suite per PDF and extraction provider."""
    spec = _spec_by_id(benchmark_id)
    if benchmark_id not in real_pdf_paths:
        pytest.skip(skip_reason(spec))

    run = run_real_pdf_benchmark(
        spec,
        real_pdf_paths[benchmark_id],
        provider=provider,  # type: ignore[arg-type]
    )
    run_benchmark_checks(run, BENCHMARK_CHECKS[benchmark_id])


@pytest.mark.real_pdf
@pytest.mark.parametrize("benchmark_id,check,provider", _CHECK_PARAMS)
def test_real_pdf_benchmark_check(
    benchmark_id: str,
    check: BenchmarkCheck,
    provider: str,
    real_pdf_paths: dict[str, Path],
) -> None:
    """Single static check for granular CI reports (pages + audit id in test name)."""
    spec = _spec_by_id(benchmark_id)
    if benchmark_id not in real_pdf_paths:
        pytest.skip(skip_reason(spec))

    run = run_real_pdf_benchmark(
        spec,
        real_pdf_paths[benchmark_id],
        provider=provider,  # type: ignore[arg-type]
    )
    check.fn(run)


@pytest.mark.real_pdf
def test_real_pdf_registry_lists_known_documents() -> None:
    ids = {spec.benchmark_id for spec in REAL_PDF_SPECS}
    assert ids == {"mondanites", "faelys"}
    for spec in REAL_PDF_SPECS:
        assert spec.benchmark_id in BENCHMARK_CHECKS
        assert BENCHMARK_CHECKS[spec.benchmark_id], "each PDF needs static checks"
