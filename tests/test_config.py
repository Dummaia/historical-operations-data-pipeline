from pathlib import Path

import pytest

from historical_operations_pipeline.config import PipelineConfig, load_config
from historical_operations_pipeline.exceptions import ConfigurationError


def test_default_config_is_valid() -> None:
    config = PipelineConfig()

    assert config.id_column == "LINE_ID"
    assert len(config.expected_sheets) == 5
    assert config.sheet_lookup["OVERDUE"] == "Overdue"


def test_load_config_reads_all_sections(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.toml"
    path.write_text(
        """
[pipeline]
file_patterns = ["*.xlsx"]
expected_sheets = ["Open"]
required_columns = ["Process Id", "Request Id", "Current Stage", "Notes", "Days", "Status"]
id_column = "Process Id"
request_column = "Request Id"
follow_up_notes_column = "Notes"
strict_sheets = false

[output]
parquet_filename = "history.parquet"
excel_filename = "history.xlsx"
quality_filename = "quality.json"

[postgres]
schema = "portfolio"
table = "history"
if_exists = "append"
chunksize = 100
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.id_column == "PROCESS_ID"
    assert config.strict_sheets is False
    assert config.postgres_if_exists == "append"
    assert config.postgres_chunksize == 100


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_id_must_be_required() -> None:
    with pytest.raises(ConfigurationError, match="ID column"):
        PipelineConfig(required_columns=("REQUEST_ID",))
