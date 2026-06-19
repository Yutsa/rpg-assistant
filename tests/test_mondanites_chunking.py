"""Legacy entry point — delegates to the real PDF benchmark registry."""

from __future__ import annotations

import pytest

from tests.fixtures.real_pdf_benchmark import (
    MONDANITES_CHECKS,
    MONDANITES_SPEC,
    resolve_real_pdf_path,
    run_benchmark_checks,
    run_real_pdf_benchmark,
    skip_reason,
)


@pytest.mark.real_pdf
@pytest.mark.skipif(
    resolve_real_pdf_path(MONDANITES_SPEC) is None,
    reason=skip_reason(MONDANITES_SPEC),
)
def test_mondanites_chunk_quality():
    pdf_path = resolve_real_pdf_path(MONDANITES_SPEC)
    assert pdf_path is not None
    run = run_real_pdf_benchmark(
        MONDANITES_SPEC,
        pdf_path,
        provider="legacy",
        document_id="doc_mondanites",
    )
    run_benchmark_checks(run, MONDANITES_CHECKS)
