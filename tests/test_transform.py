import pandas as pd
import pytest

from historical_operations_pipeline.exceptions import DataQualityError
from historical_operations_pipeline.transform import (
    add_derived_columns,
    clean_worksheet,
    deduplicate_daily_history,
    extract_follow_up_date,
    normalize_column_name,
    normalize_identifier,
)


def test_normalize_column_name_handles_accents_and_whitespace() -> None:
    assert normalize_column_name("  Área  Executiva\n") == "AREA_EXECUTIVA"
    assert normalize_column_name("Follow-up notes") == "FOLLOW_UP_NOTES"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (219175.0, "219175"),
        ("219175.00", "219175"),
        ("REQ-42", "REQ-42"),
    ],
)
def test_normalize_identifier(value: object, expected: str) -> None:
    assert normalize_identifier(value) == expected


def test_extract_follow_up_date_supports_optional_year() -> None:
    assert extract_follow_up_date("15/08/2026 - reviewed", "2026-08-18") == pd.Timestamp(
        "2026-08-15"
    )
    assert extract_follow_up_date("31/12 - reviewed", "2026-01-05") == pd.Timestamp("2025-12-31")
    assert pd.isna(extract_follow_up_date("no date", "2026-08-18"))


def test_clean_worksheet_removes_empty_ids_and_exact_duplicates() -> None:
    frame = pd.DataFrame(
        {
            "Line Id": ["1", "1", None],
            "Request Id": ["10", "10", "11"],
            "Current Stage": ["Approval", "Approval", "Intake"],
            "Follow Up Notes": ["15/08/2026 - ok", "15/08/2026 - ok", "ok"],
            "SLA Days Remaining": [2, 2, 4],
            "SLA Status": ["ON TIME", "ON TIME", "ON TIME"],
        }
    )

    result = clean_worksheet(
        frame,
        required_columns=(
            "LINE_ID",
            "REQUEST_ID",
            "CURRENT_STAGE",
            "FOLLOW_UP_NOTES",
            "SLA_DAYS_REMAINING",
            "SLA_STATUS",
        ),
        id_column="LINE_ID",
        request_column="REQUEST_ID",
        source_file="sample.xlsx",
        source_sheet="0 to 7 Days",
    )

    assert len(result.frame) == 1
    assert result.rows_without_id == 1
    assert result.exact_duplicates == 1
    assert str(result.frame["LINE_ID"].dtype) == "string"


def test_clean_worksheet_rejects_missing_contract_columns() -> None:
    with pytest.raises(DataQualityError, match="missing required"):
        clean_worksheet(
            pd.DataFrame({"LINE_ID": ["1"]}),
            required_columns=("LINE_ID", "REQUEST_ID"),
            id_column="LINE_ID",
            request_column="REQUEST_ID",
            source_file="sample.xlsx",
            source_sheet="Overdue",
        )


def test_daily_deduplication_keeps_latest_source_row() -> None:
    frame = pd.DataFrame(
        {
            "SNAPSHOT_DATE": pd.to_datetime(["2026-08-18", "2026-08-18"]),
            "SNAPSHOT_ORDER": [1, 1],
            "SHEET_ORDER": [1, 2],
            "SOURCE_ROW_NUMBER": [2, 3],
            "LINE_ID": ["LINE-1", "LINE-1"],
            "CURRENT_STAGE": ["Intake", "Approval"],
        }
    )

    result, removed = deduplicate_daily_history(frame, id_column="LINE_ID")

    assert removed == 1
    assert result.loc[0, "CURRENT_STAGE"] == "Approval"


def test_add_derived_columns_calculates_age_and_hash() -> None:
    frame = pd.DataFrame(
        {
            "SNAPSHOT_DATE": pd.to_datetime(["2026-08-18"]),
            "SNAPSHOT_ORDER": [1],
            "SOURCE_FILE": ["snapshot_2026-08-18.xlsx"],
            "SOURCE_SHEET": ["Overdue"],
            "SHEET_ORDER": [1],
            "SOURCE_ROW_NUMBER": [2],
            "LINE_ID": pd.Series(["LINE-1"], dtype="string"),
            "FOLLOW_UP_NOTES": ["15/08/2026 - reviewed"],
        }
    )

    result = add_derived_columns(frame, follow_up_notes_column="FOLLOW_UP_NOTES")

    assert result.loc[0, "FOLLOW_UP_AGE_DAYS"] == 3
    assert len(result.loc[0, "RECORD_HASH"]) == 16
