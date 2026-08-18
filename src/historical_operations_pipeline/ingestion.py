"""Workbook discovery and ingestion."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.exceptions import DataQualityError, SnapshotDateError
from historical_operations_pipeline.models import QualityReport, Severity, SnapshotSource
from historical_operations_pipeline.transform import clean_worksheet, normalize_column_name

LOGGER = logging.getLogger(__name__)

DATE_PATTERNS = (
    re.compile(r"(?<!\d)(?P<year>\d{4})[-_.](?P<month>\d{1,2})[-_.](?P<day>\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<day>\d{1,2})[-_.](?P<month>\d{1,2})[-_.](?P<year>\d{4})(?!\d)"),
)


def extract_snapshot_date(filename: str | Path) -> pd.Timestamp:
    """Infer a snapshot date from an ISO or day-first filename."""

    name = Path(filename).stem
    for pattern in DATE_PATTERNS:
        match = pattern.search(name)
        if match is None:
            continue
        try:
            return pd.Timestamp(
                year=int(match.group("year")),
                month=int(match.group("month")),
                day=int(match.group("day")),
            )
        except ValueError as exc:
            raise SnapshotDateError(f"Invalid date in filename: {filename}") from exc

    raise SnapshotDateError(
        f"Could not infer a snapshot date from '{filename}'. "
        "Use YYYY-MM-DD or DD-MM-YYYY in the filename."
    )


def discover_snapshot_files(
    input_dir: str | Path,
    *,
    config: PipelineConfig,
    report: QualityReport,
) -> list[SnapshotSource]:
    """Discover, date and deterministically order all snapshot workbooks."""

    directory = Path(input_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Input directory not found: {directory}")

    candidates: set[Path] = set()
    for pattern in config.file_patterns:
        candidates.update(
            path
            for path in directory.rglob(pattern)
            if path.is_file() and not path.name.startswith("~$")
        )

    report.files_discovered = len(candidates)
    dated_paths: list[tuple[pd.Timestamp, Path]] = []

    for path in sorted(candidates):
        try:
            snapshot_date = extract_snapshot_date(path.name)
        except SnapshotDateError as exc:
            report.add_issue(
                "SNAPSHOT_DATE_NOT_FOUND",
                Severity.WARNING,
                str(exc),
                source_file=path.name,
            )
            continue
        dated_paths.append((snapshot_date, path))

    dated_paths.sort(key=lambda item: (item[0], item[1].name.casefold(), str(item[1])))
    sources = [
        SnapshotSource(path=path, snapshot_date=snapshot_date, order=index)
        for index, (snapshot_date, path) in enumerate(dated_paths, start=1)
    ]

    if not sources:
        report.add_issue(
            "NO_INPUT_FILES",
            Severity.ERROR,
            f"No dated Excel snapshots were found in {directory}.",
        )

    LOGGER.info("Discovered %s dated snapshot workbook(s)", len(sources))
    return sources


def _sheet_map(sheet_names: list[str], source_file: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for sheet_name in sheet_names:
        key = normalize_column_name(sheet_name)
        if key in normalized:
            raise DataQualityError(
                f"{source_file} has worksheet names that collide after normalization: "
                f"'{normalized[key]}' and '{sheet_name}'."
            )
        normalized[key] = sheet_name
    return normalized


def read_snapshot(
    source: SnapshotSource,
    *,
    config: PipelineConfig,
    report: QualityReport,
) -> pd.DataFrame:
    """Read and clean every configured worksheet in one workbook."""

    frames: list[pd.DataFrame] = []
    LOGGER.info("Processing %s", source.path.name)

    try:
        with pd.ExcelFile(source.path) as workbook:
            available = _sheet_map(workbook.sheet_names, source.path.name)
            expected_keys = set(config.sheet_lookup)
            unexpected = sorted(set(available) - expected_keys)
            if unexpected:
                report.add_issue(
                    "UNEXPECTED_SHEETS",
                    Severity.INFO,
                    "Workbook contains worksheets outside the configured contract.",
                    count=len(unexpected),
                    source_file=source.path.name,
                    details={"worksheets": [available[key] for key in unexpected]},
                )

            for sheet_order, (normalized_name, expected_name) in enumerate(
                config.sheet_lookup.items(),
                start=1,
            ):
                if normalized_name not in available:
                    report.add_issue(
                        "MISSING_WORKSHEET",
                        Severity.ERROR if config.strict_sheets else Severity.WARNING,
                        f"Expected worksheet '{expected_name}' was not found.",
                        source_file=source.path.name,
                        source_sheet=expected_name,
                    )
                    continue

                real_name = available[normalized_name]
                raw = pd.read_excel(
                    workbook,
                    sheet_name=real_name,
                    dtype=object,
                )
                report.records_read += len(raw)

                try:
                    result = clean_worksheet(
                        raw,
                        required_columns=config.required_columns,
                        id_column=config.id_column,
                        request_column=config.request_column,
                        source_file=source.path.name,
                        source_sheet=real_name,
                    )
                except DataQualityError as exc:
                    report.add_issue(
                        "WORKSHEET_CONTRACT_FAILED",
                        Severity.ERROR,
                        str(exc),
                        source_file=source.path.name,
                        source_sheet=real_name,
                    )
                    continue

                report.sheets_processed += 1
                report.rows_without_id_removed += result.rows_without_id
                report.exact_duplicates_removed += result.exact_duplicates
                report.records_after_cleaning += len(result.frame)

                cleaned = result.frame
                cleaned.insert(0, "SNAPSHOT_DATE", source.snapshot_date)
                cleaned.insert(1, "SNAPSHOT_ORDER", source.order)
                cleaned.insert(2, "SOURCE_FILE", source.path.name)
                cleaned.insert(3, "SOURCE_SHEET", expected_name)
                cleaned.insert(4, "SHEET_ORDER", sheet_order)
                frames.append(cleaned)

    except (OSError, ValueError) as exc:
        report.add_issue(
            "WORKBOOK_READ_FAILED",
            Severity.ERROR,
            f"Could not read workbook: {exc}",
            source_file=source.path.name,
        )
        return pd.DataFrame()

    report.files_processed += 1
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def load_snapshots(
    sources: list[SnapshotSource],
    *,
    config: PipelineConfig,
    report: QualityReport,
) -> pd.DataFrame:
    """Load all workbooks into one lineage-preserving DataFrame."""

    snapshots = [
        snapshot
        for source in sources
        if not (
            snapshot := read_snapshot(
                source,
                config=config,
                report=report,
            )
        ).empty
    ]
    if not snapshots:
        return pd.DataFrame()
    return pd.concat(snapshots, ignore_index=True, sort=False)
