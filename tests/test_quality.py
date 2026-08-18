import pandas as pd
import pytest

from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.exceptions import DataQualityError
from historical_operations_pipeline.models import QualityReport, Severity
from historical_operations_pipeline.quality import (
    raise_for_quality_errors,
    validate_history,
)


def test_empty_history_is_blocking() -> None:
    report = QualityReport()
    validate_history(pd.DataFrame(), config=PipelineConfig(), report=report)

    assert report.error_count == 1
    with pytest.raises(DataQualityError, match="quality error"):
        raise_for_quality_errors(report)


def test_report_serialization_contains_metrics() -> None:
    report = QualityReport(files_discovered=2)
    report.add_issue(
        "EXAMPLE",
        Severity.WARNING,
        "Example warning",
        count=3,
    )
    report.finish()

    payload = report.to_dict()

    assert payload["status"] == "passed"
    assert payload["metrics"]["warnings"] == 3
    assert payload["metrics"]["files_discovered"] == 2
