"""Generate the safe sample workbooks used by the README quick start."""

from historical_operations_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["generate-sample"]))
