"""Data models shared across pipeline modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd


class Severity(StrEnum):
    """Quality issue severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class QualityIssue:
    """A single data-quality observation."""

    code: str
    severity: Severity
    message: str
    count: int = 1
    source_file: str | None = None
    source_sheet: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        payload = asdict(self)
        payload["severity"] = self.severity.value
        return payload


@dataclass(slots=True)
class QualityReport:
    """Aggregated processing metrics and quality issues."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    files_discovered: int = 0
    files_processed: int = 0
    sheets_processed: int = 0
    records_read: int = 0
    records_after_cleaning: int = 0
    records_in_history: int = 0
    rows_without_id_removed: int = 0
    exact_duplicates_removed: int = 0
    daily_duplicates_removed: int = 0
    issues: list[QualityIssue] = field(default_factory=list)

    def add_issue(
        self,
        code: str,
        severity: Severity,
        message: str,
        *,
        count: int = 1,
        source_file: str | None = None,
        source_sheet: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append an issue without exposing report internals to callers."""

        self.issues.append(
            QualityIssue(
                code=code,
                severity=severity,
                message=message,
                count=count,
                source_file=source_file,
                source_sheet=source_sheet,
                details=details or {},
            )
        )

    @property
    def error_count(self) -> int:
        return sum(issue.count for issue in self.issues if issue.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(issue.count for issue in self.issues if issue.severity is Severity.WARNING)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def finish(self) -> None:
        """Mark processing as complete."""

        self.finished_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Return a stable, JSON-compatible report."""

        duration_seconds = None
        if self.finished_at is not None:
            duration_seconds = round((self.finished_at - self.started_at).total_seconds(), 3)

        return {
            "status": "passed" if self.passed else "failed",
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": duration_seconds,
            "metrics": {
                "files_discovered": self.files_discovered,
                "files_processed": self.files_processed,
                "sheets_processed": self.sheets_processed,
                "records_read": self.records_read,
                "records_after_cleaning": self.records_after_cleaning,
                "records_in_history": self.records_in_history,
                "rows_without_id_removed": self.rows_without_id_removed,
                "exact_duplicates_removed": self.exact_duplicates_removed,
                "daily_duplicates_removed": self.daily_duplicates_removed,
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def issues_frame(self) -> pd.DataFrame:
        """Return issues as a DataFrame for the Excel output."""

        rows = [issue.to_dict() for issue in self.issues]
        if not rows:
            return pd.DataFrame(
                columns=[
                    "code",
                    "severity",
                    "message",
                    "count",
                    "source_file",
                    "source_sheet",
                    "details",
                ]
            )

        frame = pd.DataFrame(rows)
        frame["details"] = frame["details"].map(str)
        return frame


@dataclass(frozen=True, slots=True)
class SnapshotSource:
    """A dated workbook discovered in the input directory."""

    path: Path
    snapshot_date: pd.Timestamp
    order: int


@dataclass(slots=True)
class CleanFrameResult:
    """Cleaned worksheet plus row-level cleaning counters."""

    frame: pd.DataFrame
    raw_rows: int
    rows_without_id: int
    exact_duplicates: int


@dataclass(slots=True)
class PipelineResult:
    """All in-memory outputs created by one pipeline execution."""

    history: pd.DataFrame
    latest_position: pd.DataFrame
    summary: pd.DataFrame
    quality_report: QualityReport
    output_paths: dict[str, Path] = field(default_factory=dict)
