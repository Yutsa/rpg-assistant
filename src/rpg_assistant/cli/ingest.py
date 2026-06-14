from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rpg_assistant.dev.demo_seed import seed_demo_data
from rpg_assistant.ingestion.raw.importer import run
from rpg_assistant.storage.db import get_connection
from rpg_assistant.storage.repositories.raw import RawRepository


def _cmd_raw_extract(args: argparse.Namespace) -> int:
    result = run(
        Path(args.pdf),
        campaign_id=args.campaign_id,
        campaign_title=args.campaign_title or "",
        game_system=args.game_system or "",
        coverage_threshold=args.coverage_threshold,
        reimport=not args.no_reimport,
    )
    print(json.dumps(result.__dict__, indent=2, default=str))
    return 0 if result.status == "completed" else 1


def _cmd_raw_status(args: argparse.Namespace) -> int:
    with get_connection() as conn:
        repo = RawRepository(conn)
        run_record = repo.get_ingestion_run(args.ingestion_run_id)
    if not run_record:
        print(f"Ingestion run not found: {args.ingestion_run_id}", file=sys.stderr)
        return 1
    print(json.dumps(run_record.model_dump(), indent=2, default=str))
    return 0


def _cmd_demo_seed(args: argparse.Namespace) -> int:
    result = seed_demo_data(reset=not args.keep_existing)
    print(
        "Demo data seeded:\n"
        f"  campaign: {result['campaign_id']}\n"
        f"  document: {result['document_id']}\n"
        f"  pdf:      {result['pdf_path']}\n"
        "\nOpen http://127.0.0.1:8000 and explore the Momie campaign."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RPG Assistant ingestion CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    raw = sub.add_parser("raw", help="Raw deterministic extraction")
    raw_sub = raw.add_subparsers(dest="raw_command", required=True)

    extract = raw_sub.add_parser("extract", help="Extract PDF into raw layer")
    extract.add_argument("pdf", type=Path, help="Path to campaign PDF")
    extract.add_argument("--campaign-id", required=True, help="Campaign identifier")
    extract.add_argument("--campaign-title", default="", help="Campaign title")
    extract.add_argument("--game-system", default="", help="Game system name")
    extract.add_argument(
        "--coverage-threshold",
        type=float,
        default=0.3,
        help="Minimum text coverage ratio (default: 0.3)",
    )
    extract.add_argument(
        "--no-reimport",
        action="store_true",
        help="Skip deleting existing raw data for the same document hash",
    )
    extract.set_defaults(func=_cmd_raw_extract)

    status = raw_sub.add_parser("status", help="Show ingestion run status")
    status.add_argument("--ingestion-run-id", required=True)
    status.set_defaults(func=_cmd_raw_status)

    demo = sub.add_parser("demo", help="Demo / development helpers")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    seed = demo_sub.add_parser("seed", help="Insert fake exploration data for local UI testing")
    seed.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not reset the demo campaign before seeding",
    )
    seed.set_defaults(func=_cmd_demo_seed)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
