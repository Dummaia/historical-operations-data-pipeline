"""Minimal Python API example."""

from historical_operations_pipeline import load_config, run_pipeline
from historical_operations_pipeline.sample_data import generate_sample_snapshots

generate_sample_snapshots("data/sample", snapshots=3)

result = run_pipeline(
    "data/sample",
    output_dir="output",
    config=load_config("config/pipeline.toml"),
)

print(result.summary)
