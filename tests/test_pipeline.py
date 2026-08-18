import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from historical_operations_pipeline.cli import main
from historical_operations_pipeline.config import PipelineConfig
from historical_operations_pipeline.pipeline import run_pipeline


def test_pipeline_end_to_end(sample_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"

    result = run_pipeline(
        sample_dir,
        output_dir=output,
        config=PipelineConfig(),
    )

    assert len(result.history) == 54
    assert len(result.latest_position) == 18
    assert result.quality_report.passed
    assert result.history.groupby(["SNAPSHOT_DATE", "LINE_ID"]).size().max() == 1

    parquet = pd.read_parquet(result.output_paths["parquet"])
    assert len(parquet) == 54
    assert set(pd.ExcelFile(result.output_paths["excel"]).sheet_names) == {
        "history",
        "latest_position",
        "summary",
        "quality_issues",
    }
    workbook = load_workbook(result.output_paths["excel"])
    history_sheet = workbook["history"]
    assert history_sheet.freeze_panes == "A2"
    assert history_sheet["A2"].number_format == "yyyy-mm-dd"
    assert history_sheet["A1"].fill.fgColor.rgb.endswith("172554")

    quality = json.loads(result.output_paths["quality"].read_text(encoding="utf-8"))
    assert quality["status"] == "passed"
    assert quality["metrics"]["files_processed"] == 3


def test_cli_generates_and_processes_samples(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    sample = tmp_path / "sample"
    output = tmp_path / "output"
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert (
        main(
            [
                "generate-sample",
                "--output",
                str(sample),
                "--snapshots",
                "2",
                "--records",
                "18",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "run",
                "--input",
                str(sample),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "Pipeline completed successfully" in captured.out
    assert (output / "historical_operations.parquet").is_file()
