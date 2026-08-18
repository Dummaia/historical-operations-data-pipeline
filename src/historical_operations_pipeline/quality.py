"""Post-transformation quality checks."""

from __future__ import annotations

import pandas as pd

from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.exceptions import DataQualityError
from historical_operations_pipeline.models import QualityReport, Severity


def validate_history(
    history: pd.DataFrame,
    *,
    config: PipelineConfig,
    report: QualityReport,
) -> None:
    """Validate invariants expected from the consolidated historical table."""

    report.records_in_history = len(history)
    if history.empty:
        report.add_issue(
            "EMPTY_HISTORY",
            Severity.ERROR,
            "The pipeline did not produce historical records.",
        )
        return

    required_output = {
        "SNAPSHOT_DATE",
        "SNAPSHOT_ORDER",
        "SOURCE_FILE",
        "SOURCE_SHEET",
        "SOURCE_ROW_NUMBER",
        config.id_column,
        "RECORD_HASH",
    }
    missing = sorted(required_output - set(history.columns))
    if missing:
        report.add_issue(
            "OUTPUT_CONTRACT_FAILED",
            Severity.ERROR,
            f"Historical output is missing columns: {', '.join(missing)}",
            count=len(missing),
        )

    null_ids = int(history[config.id_column].isna().sum())
    if null_ids:
        report.add_issue(
            "NULL_PROCESS_ID",
            Severity.ERROR,
            "Historical output contains records without a process identifier.",
            count=null_ids,
        )

    daily_duplicates = int(
        history.duplicated(["SNAPSHOT_DATE", config.id_column], keep=False).sum()
    )
    if daily_duplicates:
        report.add_issue(
            "DUPLICATE_DAILY_PROCESS",
            Severity.ERROR,
            "More than one record remains for the same process and snapshot date.",
            count=daily_duplicates,
        )

    invalid_snapshot_dates = int(history["SNAPSHOT_DATE"].isna().sum())
    if invalid_snapshot_dates:
        report.add_issue(
            "INVALID_SNAPSHOT_DATE",
            Severity.ERROR,
            "Historical output contains invalid snapshot dates.",
            count=invalid_snapshot_dates,
        )

    if "FOLLOW_UP_AGE_DAYS" in history.columns:
        future_follow_ups = int((history["FOLLOW_UP_AGE_DAYS"] < 0).fillna(False).sum())
        if future_follow_ups:
            report.add_issue(
                "FUTURE_FOLLOW_UP_DATE",
                Severity.WARNING,
                "A follow-up date occurs after its snapshot date.",
                count=future_follow_ups,
            )

    if "SLA_DAYS_REMAINING" in history.columns:
        invalid_sla = int(history["SLA_DAYS_REMAINING"].isna().sum())
        if invalid_sla:
            report.add_issue(
                "INVALID_SLA_VALUE",
                Severity.WARNING,
                "SLA days could not be parsed for some records.",
                count=invalid_sla,
            )

    missing_follow_up = int(history[config.follow_up_notes_column].isna().sum())
    if missing_follow_up:
        report.add_issue(
            "MISSING_FOLLOW_UP",
            Severity.INFO,
            "Some processes do not contain follow-up notes.",
            count=missing_follow_up,
        )


def raise_for_quality_errors(report: QualityReport) -> None:
    """Fail the run when one or more blocking rules were violated."""

    if report.error_count:
        raise DataQualityError(f"Pipeline blocked by {report.error_count} data-quality error(s).")
