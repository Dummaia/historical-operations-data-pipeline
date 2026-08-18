from pathlib import Path

import pandas as pd
import pytest

from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.exceptions import SnapshotDateError
from historical_operations_pipeline.ingestion import (
    discover_snapshot_files,
    extract_snapshot_date,
    load_snapshots,
)
from historical_operations_pipeline.models import QualityReport


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("operations_2026-08-18.xlsx", "2026-08-18"),
        ("operations_18.08.2026.xlsm", "2026-08-18"),
        ("snapshot_18_08_2026.xlsx", "2026-08-18"),
    ],
)
def test_extract_snapshot_date(filename: str, expected: str) -> None:
    assert extract_snapshot_date(filename) == pd.Timestamp(expected)


def test_invalid_snapshot_date_fails() -> None:
    with pytest.raises(SnapshotDateError, match="Invalid date"):
        extract_snapshot_date("operations_31-02-2026.xlsx")

    with pytest.raises(SnapshotDateError, match="Could not infer"):
        extract_snapshot_date("operations_latest.xlsx")


def test_discovery_skips_undated_files(sample_dir: Path) -> None:
    (sample_dir / "notes.xlsx").touch()
    report = QualityReport()

    sources = discover_snapshot_files(
        sample_dir,
        config=PipelineConfig(),
        report=report,
    )

    assert len(sources) == 3
    assert [source.order for source in sources] == [1, 2, 3]
    assert any(issue.code == "SNAPSHOT_DATE_NOT_FOUND" for issue in report.issues)


def test_load_snapshots_adds_lineage(sample_dir: Path) -> None:
    config = PipelineConfig()
    report = QualityReport()
    sources = discover_snapshot_files(sample_dir, config=config, report=report)

    frame = load_snapshots(sources, config=config, report=report)

    assert len(frame) == 54
    assert {
        "SNAPSHOT_DATE",
        "SNAPSHOT_ORDER",
        "SOURCE_FILE",
        "SOURCE_SHEET",
        "SHEET_ORDER",
        "SOURCE_ROW_NUMBER",
    }.issubset(frame.columns)
    assert report.files_processed == 3
    assert report.sheets_processed == 15
