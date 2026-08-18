"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ only
    import tomli as tomllib

from historical_operations_pipeline.exceptions import ConfigurationError
from historical_operations_pipeline.transform import normalize_column_name

DEFAULT_SHEETS = (
    "Overdue",
    "0 to 7 Days",
    "8 to 15 Days",
    "16 to 25 Days",
    "26 to 35 Days",
)

DEFAULT_REQUIRED_COLUMNS = (
    "LINE_ID",
    "REQUEST_ID",
    "CURRENT_STAGE",
    "FOLLOW_UP_NOTES",
    "SLA_DAYS_REMAINING",
    "SLA_STATUS",
)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Validated pipeline settings."""

    file_patterns: tuple[str, ...] = ("*.xlsx", "*.xlsm")
    expected_sheets: tuple[str, ...] = DEFAULT_SHEETS
    required_columns: tuple[str, ...] = DEFAULT_REQUIRED_COLUMNS
    id_column: str = "LINE_ID"
    request_column: str = "REQUEST_ID"
    follow_up_notes_column: str = "FOLLOW_UP_NOTES"
    strict_sheets: bool = True
    parquet_filename: str = "historical_operations.parquet"
    excel_filename: str = "historical_operations.xlsx"
    quality_filename: str = "quality_report.json"
    postgres_schema: str = "analytics"
    postgres_table: str = "historical_operations"
    postgres_if_exists: str = "replace"
    postgres_chunksize: int = 5000
    sheet_lookup: dict[str, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        normalized_required = tuple(normalize_column_name(name) for name in self.required_columns)
        object.__setattr__(self, "required_columns", normalized_required)
        object.__setattr__(self, "id_column", normalize_column_name(self.id_column))
        object.__setattr__(self, "request_column", normalize_column_name(self.request_column))
        object.__setattr__(
            self,
            "follow_up_notes_column",
            normalize_column_name(self.follow_up_notes_column),
        )
        object.__setattr__(
            self,
            "sheet_lookup",
            {normalize_column_name(name): name for name in self.expected_sheets},
        )
        self._validate()

    def _validate(self) -> None:
        if not self.file_patterns:
            raise ConfigurationError("At least one input file pattern is required.")
        if not self.expected_sheets:
            raise ConfigurationError("At least one worksheet must be configured.")
        if len(self.sheet_lookup) != len(self.expected_sheets):
            raise ConfigurationError("Worksheet names must remain unique after normalization.")
        if self.id_column not in self.required_columns:
            raise ConfigurationError("The ID column must be listed in required_columns.")
        if self.postgres_if_exists not in {"fail", "replace", "append"}:
            raise ConfigurationError("postgres.if_exists must be fail, replace or append.")
        if self.postgres_chunksize < 1:
            raise ConfigurationError("postgres.chunksize must be greater than zero.")
        for filename in (
            self.parquet_filename,
            self.excel_filename,
            self.quality_filename,
        ):
            if Path(filename).name != filename:
                raise ConfigurationError("Output filenames cannot contain directories.")

    def with_strict_sheets(self, strict: bool) -> PipelineConfig:
        """Return a copy with the CLI strictness override applied."""

        return replace(self, strict_sheets=strict)


def _section(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"The [{name}] section must be a TOML table.")
    return value


def load_config(path: str | Path | None = None) -> PipelineConfig:
    """Load TOML configuration or return safe defaults."""

    if path is None:
        return PipelineConfig()

    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    with config_path.open("rb") as stream:
        payload = tomllib.load(stream)

    pipeline = _section(payload, "pipeline")
    output = _section(payload, "output")
    postgres = _section(payload, "postgres")

    return PipelineConfig(
        file_patterns=tuple(pipeline.get("file_patterns", ("*.xlsx", "*.xlsm"))),
        expected_sheets=tuple(pipeline.get("expected_sheets", DEFAULT_SHEETS)),
        required_columns=tuple(pipeline.get("required_columns", DEFAULT_REQUIRED_COLUMNS)),
        id_column=pipeline.get("id_column", "LINE_ID"),
        request_column=pipeline.get("request_column", "REQUEST_ID"),
        follow_up_notes_column=pipeline.get(
            "follow_up_notes_column",
            "FOLLOW_UP_NOTES",
        ),
        strict_sheets=bool(pipeline.get("strict_sheets", True)),
        parquet_filename=output.get(
            "parquet_filename",
            "historical_operations.parquet",
        ),
        excel_filename=output.get(
            "excel_filename",
            "historical_operations.xlsx",
        ),
        quality_filename=output.get("quality_filename", "quality_report.json"),
        postgres_schema=postgres.get("schema", "analytics"),
        postgres_table=postgres.get("table", "historical_operations"),
        postgres_if_exists=postgres.get("if_exists", "replace"),
        postgres_chunksize=int(postgres.get("chunksize", 5000)),
    )
