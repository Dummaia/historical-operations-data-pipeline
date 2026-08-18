"""Pipeline orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.ingestion import (
    discover_snapshot_files,
    load_snapshots,
)
from historical_operations_pipeline.models import PipelineResult, QualityReport, Severity
from historical_operations_pipeline.quality import (
    raise_for_quality_errors,
    validate_history,
)
from historical_operations_pipeline.storage import write_outputs, write_postgres
from historical_operations_pipeline.transform import (
    add_derived_columns,
    build_latest_position,
    build_summary,
    deduplicate_daily_history,
)

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    input_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    config: PipelineConfig | None = None,
    database_url: str | None = None,
) -> PipelineResult:
    """Execute discovery, ingestion, transformation, validation and persistence."""

    active_config = config or PipelineConfig()
    report = QualityReport()

    sources = discover_snapshot_files(
        input_dir,
        config=active_config,
        report=report,
    )
    raw_history = load_snapshots(
        sources,
        config=active_config,
        report=report,
    )
    daily_history, removed = deduplicate_daily_history(
        raw_history,
        id_column=active_config.id_column,
    )
    report.daily_duplicates_removed = removed
    if removed:
        report.add_issue(
            "DAILY_DUPLICATES_RESOLVED",
            Severity.INFO,
            "Multiple same-day appearances were resolved by keeping the latest source row.",
            count=removed,
        )

    history = add_derived_columns(
        daily_history,
        follow_up_notes_column=active_config.follow_up_notes_column,
    )
    validate_history(
        history,
        config=active_config,
        report=report,
    )
    latest_position = build_latest_position(
        history,
        id_column=active_config.id_column,
    )
    summary = build_summary(
        history,
        id_column=active_config.id_column,
    )
    report.finish()

    result = PipelineResult(
        history=history,
        latest_position=latest_position,
        summary=summary,
        quality_report=report,
    )

    raise_for_quality_errors(report)

    if output_dir is not None:
        write_outputs(
            result,
            output_dir=output_dir,
            config=active_config,
        )

    if database_url:
        write_postgres(
            history,
            database_url=database_url,
            config=active_config,
        )

    LOGGER.info(
        "Pipeline completed: %s files, %s historical records, %s current processes",
        report.files_processed,
        len(history),
        len(latest_position),
    )
    return result
