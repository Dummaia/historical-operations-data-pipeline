"""Pure transformations for operational snapshot data."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import pandas as pd

from historical_operations_pipeline.exceptions import DataQualityError
from historical_operations_pipeline.models import CleanFrameResult

TECHNICAL_COLUMNS = {
    "SNAPSHOT_DATE",
    "SNAPSHOT_ORDER",
    "SOURCE_FILE",
    "SOURCE_SHEET",
    "SHEET_ORDER",
    "SOURCE_ROW_NUMBER",
    "RECORD_HASH",
    "FOLLOW_UP_DATE",
    "FOLLOW_UP_AGE_DAYS",
}


def normalize_column_name(value: Any) -> str:
    """Convert a column or sheet label to stable `UPPER_SNAKE_CASE`."""

    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.strip().upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def normalize_identifier(value: Any) -> Any:
    """Preserve identifiers as text while removing Excel's trailing `.0`."""

    if pd.isna(value):
        return pd.NA

    text = str(value).strip()
    if not text:
        return pd.NA
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", maxsplit=1)[0]
    return text


def _duplicate_names(names: Iterable[str]) -> list[str]:
    counts = Counter(names)
    return sorted(name for name, count in counts.items() if count > 1)


def clean_worksheet(
    frame: pd.DataFrame,
    *,
    required_columns: tuple[str, ...],
    id_column: str,
    request_column: str,
    source_file: str,
    source_sheet: str,
) -> CleanFrameResult:
    """Normalize one worksheet and enforce its minimum data contract."""

    cleaned = frame.copy()
    raw_rows = len(cleaned)

    normalized_columns = [normalize_column_name(column) for column in cleaned.columns]
    duplicates = _duplicate_names(normalized_columns)
    if duplicates:
        raise DataQualityError(
            f"{source_file} / {source_sheet} has colliding columns after normalization: "
            f"{', '.join(duplicates)}"
        )
    cleaned.columns = normalized_columns

    removable = [column for column in cleaned.columns if not column or column.startswith("UNNAMED")]
    cleaned = cleaned.drop(columns=removable, errors="ignore")
    cleaned = cleaned.dropna(axis=1, how="all")
    cleaned = cleaned.dropna(axis=0, how="all")
    cleaned["SOURCE_ROW_NUMBER"] = cleaned.index + 2

    for column in cleaned.columns:
        if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(
            cleaned[column]
        ):
            cleaned[column] = cleaned[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

    cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True)

    missing_columns = sorted(set(required_columns) - set(cleaned.columns))
    if missing_columns:
        raise DataQualityError(
            f"{source_file} / {source_sheet} is missing required columns: "
            f"{', '.join(missing_columns)}"
        )

    rows_without_id = int(cleaned[id_column].isna().sum())
    cleaned = cleaned.loc[cleaned[id_column].notna()].copy()

    for column in (id_column, request_column):
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].map(normalize_identifier).astype("string")

    if "SLA_DAYS_REMAINING" in cleaned.columns:
        cleaned["SLA_DAYS_REMAINING"] = pd.to_numeric(
            cleaned["SLA_DAYS_REMAINING"],
            errors="coerce",
        ).astype("Int64")

    for column in ("START_DATE", "DUE_DATE"):
        if column in cleaned.columns:
            cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce").dt.normalize()

    comparison_columns = [column for column in cleaned.columns if column != "SOURCE_ROW_NUMBER"]
    before_deduplication = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=comparison_columns, keep="last")
    exact_duplicates = before_deduplication - len(cleaned)

    return CleanFrameResult(
        frame=cleaned.reset_index(drop=True),
        raw_rows=raw_rows,
        rows_without_id=rows_without_id,
        exact_duplicates=exact_duplicates,
    )


def extract_follow_up_date(value: Any, snapshot_date: Any) -> pd.Timestamp:
    """Extract the first `DD/MM[/YYYY]` date from a follow-up note."""

    if pd.isna(value) or pd.isna(snapshot_date):
        return pd.NaT

    if isinstance(value, (date, datetime, pd.Timestamp)):
        return pd.Timestamp(value).normalize()

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", str(value))
    if not match:
        return pd.NaT

    day = int(match.group(1))
    month = int(match.group(2))
    year_text = match.group(3)
    snapshot = pd.Timestamp(snapshot_date).normalize()

    if year_text is None:
        year = snapshot.year
    else:
        year = int(year_text)
        if year < 100:
            year += 2000

    try:
        candidate = pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return pd.NaT

    if year_text is None and candidate > snapshot + pd.Timedelta(days=31):
        candidate = candidate.replace(year=year - 1)

    return candidate.normalize()


def _record_hash(frame: pd.DataFrame) -> pd.Series:
    business_columns = sorted(column for column in frame.columns if column not in TECHNICAL_COLUMNS)
    stable_values = frame[business_columns].astype("string").fillna("<NA>")
    hashes = pd.util.hash_pandas_object(stable_values, index=False)
    return hashes.map(lambda value: f"{int(value):016x}").astype("string")


def add_derived_columns(
    history: pd.DataFrame,
    *,
    follow_up_notes_column: str,
) -> pd.DataFrame:
    """Add follow-up dates, age and a deterministic business-record hash."""

    if history.empty:
        return history.copy()

    enriched = history.copy()
    enriched["FOLLOW_UP_DATE"] = [
        extract_follow_up_date(note, snapshot)
        for note, snapshot in zip(
            enriched[follow_up_notes_column],
            enriched["SNAPSHOT_DATE"],
            strict=True,
        )
    ]
    enriched["FOLLOW_UP_DATE"] = pd.to_datetime(
        enriched["FOLLOW_UP_DATE"],
        errors="coerce",
    ).dt.normalize()

    age = enriched["SNAPSHOT_DATE"] - enriched["FOLLOW_UP_DATE"]
    enriched["FOLLOW_UP_AGE_DAYS"] = age.dt.days.astype("Int64")
    enriched["RECORD_HASH"] = _record_hash(enriched)
    return enriched


def deduplicate_daily_history(
    history: pd.DataFrame,
    *,
    id_column: str,
) -> tuple[pd.DataFrame, int]:
    """Keep the last appearance of each process on each snapshot date."""

    if history.empty:
        return history.copy(), 0

    sort_columns = [
        "SNAPSHOT_DATE",
        "SNAPSHOT_ORDER",
        "SHEET_ORDER",
        "SOURCE_ROW_NUMBER",
    ]
    ordered = history.sort_values(sort_columns, kind="stable", na_position="last")
    deduplicated = ordered.drop_duplicates(
        subset=["SNAPSHOT_DATE", id_column],
        keep="last",
    )
    removed = len(ordered) - len(deduplicated)
    deduplicated = deduplicated.sort_values(
        ["SNAPSHOT_DATE", id_column],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    return deduplicated, removed


def build_latest_position(history: pd.DataFrame, *, id_column: str) -> pd.DataFrame:
    """Return the most recent record for every process."""

    if history.empty:
        return history.copy()

    return (
        history.sort_values(
            ["SNAPSHOT_DATE", "SNAPSHOT_ORDER", "SHEET_ORDER", "SOURCE_ROW_NUMBER"],
            kind="stable",
            na_position="last",
        )
        .drop_duplicates(subset=[id_column], keep="last")
        .sort_values(["SNAPSHOT_DATE", id_column], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )


def build_summary(history: pd.DataFrame, *, id_column: str = "LINE_ID") -> pd.DataFrame:
    """Aggregate the historical output by snapshot and source sheet."""

    if history.empty:
        return pd.DataFrame(
            columns=[
                "SNAPSHOT_DATE",
                "SOURCE_FILE",
                "SOURCE_SHEET",
                "RECORD_COUNT",
                "UNIQUE_PROCESSES",
            ]
        )

    return (
        history.groupby(
            ["SNAPSHOT_DATE", "SOURCE_FILE", "SOURCE_SHEET"],
            dropna=False,
            sort=True,
        )
        .agg(
            RECORD_COUNT=(id_column, "size"),
            UNIQUE_PROCESSES=(id_column, "nunique"),
        )
        .reset_index()
        .sort_values(["SNAPSHOT_DATE", "SOURCE_SHEET"], kind="stable")
        .reset_index(drop=True)
    )
