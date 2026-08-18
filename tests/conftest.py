from pathlib import Path

import pytest

from historical_operations_pipeline.sample_data import generate_sample_snapshots


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "snapshots"
    generate_sample_snapshots(directory, snapshots=3, records=18)
    return directory
