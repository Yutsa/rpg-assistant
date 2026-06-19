from __future__ import annotations

import re

import pytest

from rpg_ingest.raw.pymupdf4llm_extractor import (
    _classify_box,
    _markdown_heading_level,
)


@pytest.mark.parametrize(
    ("markdown", "pos", "expected"),
    [
        ("## Chapter 1\n\nBody", 0, 2),
        ("# Title\n\n## Sub", 10, 2),
        ("Plain text", 0, 1),
    ],
)
def test_markdown_heading_level(markdown: str, pos: int, expected: int):
    assert _markdown_heading_level(markdown, pos) == expected


def test_classify_box_heading_and_table():
    kind, level = _classify_box(
        "section-header",
        "Chapter 1",
        markdown_text="## Chapter 1\n\nBody",
        markdown_pos=(0, 13),
    )
    assert kind == "heading"
    assert level == 2

    kind, level = _classify_box(
        "table",
        "|A|B|",
        markdown_text="",
        markdown_pos=None,
    )
    assert kind == "table"
    assert level is None


def test_classify_box_stat_block_candidate():
    kind, _ = _classify_box(
        "text",
        "Momie | NC 12",
        markdown_text="",
        markdown_pos=None,
    )
    assert kind == "stat_block_candidate"
