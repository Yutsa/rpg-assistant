#!/usr/bin/env python3
"""Estimate the number of model tokens in a PDF's extracted text."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_MODEL = "gpt-5-mini"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF and estimate its token count."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file to inspect.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model name used for tokenization. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--text-preview",
        type=int,
        default=0,
        metavar="CHARS",
        help="Print the first CHARS extracted characters for sanity checking.",
    )
    return parser.parse_args()


def load_dependencies():
    try:
        import pymupdf
    except ImportError:
        print(
            "Missing dependency: pymupdf\n"
            "Install dependencies with: pip install pymupdf tiktoken",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        import tiktoken
    except ImportError:
        print(
            "Missing dependency: tiktoken\n"
            "Install dependencies with: pip install pymupdf tiktoken",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return pymupdf, tiktoken


def extract_text(pdf_path: Path, pymupdf) -> tuple[str, int]:
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        print(f"Could not open PDF: {exc}", file=sys.stderr)
        raise SystemExit(1)

    pages = []
    for page in document:
        pages.append(page.get_text())

    return "\n".join(pages), document.page_count


def encoding_for_model(model: str, tiktoken):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        print(
            f"Unknown model for tiktoken: {model}\n"
            "Falling back to the cl100k_base encoding.",
            file=sys.stderr,
        )
        return tiktoken.get_encoding("cl100k_base")


def main() -> int:
    args = parse_args()

    if not args.pdf.exists():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    if not args.pdf.is_file():
        print(f"Path is not a file: {args.pdf}", file=sys.stderr)
        return 1

    pymupdf, tiktoken = load_dependencies()
    text, page_count = extract_text(args.pdf, pymupdf)
    encoding = encoding_for_model(args.model, tiktoken)
    token_count = len(encoding.encode(text))

    print(f"File: {args.pdf}")
    print(f"Model: {args.model}")
    print(f"Pages: {page_count:,}")
    print(f"Extracted characters: {len(text):,}")
    print(f"Estimated tokens: {token_count:,}")

    if page_count:
        print(f"Estimated tokens/page: {round(token_count / page_count):,}")

    if args.text_preview > 0:
        print("\nText preview:")
        print(text[: args.text_preview])

    if not text.strip():
        print(
            "\nNo text was extracted. This PDF may be scanned or image-based and may need OCR.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
