"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from historical_operations_pipeline import __version__
from historical_operations_pipeline.config import load_config
from historical_operations_pipeline.exceptions import PipelineError
from historical_operations_pipeline.pipeline import run_pipeline
from historical_operations_pipeline.sample_data import generate_sample_snapshots


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="historical-pipeline",
        description="Build a traceable history from multi-sheet Excel snapshots.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample = subparsers.add_parser(
        "generate-sample",
        help="Generate fictitious workbooks for a safe local demonstration.",
    )
    sample.add_argument("--output", type=Path, default=Path("data/sample"))
    sample.add_argument("--snapshots", type=int, default=3)
    sample.add_argument("--records", type=int, default=27)
    sample.add_argument("--start-date", default="2026-08-01")

    run = subparsers.add_parser("run", help="Execute the ETL pipeline.")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, default=Path("output"))
    run.add_argument("--config", type=Path)
    run.add_argument(
        "--strict-sheets",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override the worksheet strictness configured in TOML.",
    )
    run.add_argument(
        "--database-url",
        help="Optional SQLAlchemy PostgreSQL URL; defaults to DATABASE_URL.",
    )
    run.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )

    return parser


def _run_command(args: argparse.Namespace) -> int:
    _configure_logging(args.log_level)
    config = load_config(args.config)
    if args.strict_sheets is not None:
        config = config.with_strict_sheets(args.strict_sheets)

    result = run_pipeline(
        args.input,
        output_dir=args.output,
        config=config,
        database_url=args.database_url or os.getenv("DATABASE_URL"),
    )
    print()
    print("Pipeline completed successfully")
    print(f"  Snapshots processed : {result.quality_report.files_processed}")
    print(f"  Historical records  : {len(result.history)}")
    print(f"  Current processes   : {len(result.latest_position)}")
    print(f"  Quality status      : {'PASSED' if result.quality_report.passed else 'FAILED'}")
    for name, path in result.output_paths.items():
        print(f"  {name:<20}: {path}")
    return 0


def _sample_command(args: argparse.Namespace) -> int:
    paths = generate_sample_snapshots(
        args.output,
        snapshots=args.snapshots,
        records=args.records,
        start_date=args.start_date,
    )
    print(f"Created {len(paths)} synthetic snapshot workbook(s):")
    for path in paths:
        print(f"  {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "generate-sample":
            return _sample_command(args)
        return _run_command(args)
    except (OSError, ValueError, PipelineError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 2
