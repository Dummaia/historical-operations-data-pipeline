# Historical Operations Data Pipeline

[![CI](https://github.com/Dummaia/historical-operations-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Dummaia/historical-operations-data-pipeline/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-ETL-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-optional-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)

Production-ready Python ETL pipeline that turns dated, multi-sheet Excel
snapshots into a reliable historical dataset with lineage, data-quality checks
and analytics-ready outputs.

> **Portfolio edition:** the architecture and business logic are based on a
> real operational solution. All names, paths, identifiers and sample records
> in this repository are fictitious. No corporate data or credentials are
> included.

[Versão em português](docs/README.pt-BR.md) ·
[Architecture](docs/architecture.md) ·
[Data dictionary](docs/data-dictionary.md) ·
[Quality rules](docs/quality-rules.md)

## Why this project exists

Files do not become history simply because they are stored over time. A useful
history needs a repeatable process to discover each snapshot, standardize its
schema, enforce quality rules, select the correct daily state and preserve
where every record came from.

The original implementation consolidated **64,432+ records from 12 workbooks**
while keeping the source files unchanged. This public version makes the same
engineering pattern reproducible with generated data.

## What it does

- Discovers `.xlsx` and `.xlsm` snapshots recursively.
- Extracts the reference date from each filename.
- Reads five operational SLA worksheets from every workbook.
- Normalizes column names, identifiers, text, numbers and dates.
- Rejects broken schemas and reports missing worksheets.
- Removes empty rows, invalid process rows and exact duplicates.
- Keeps the latest appearance of each process on each snapshot date.
- Preserves file, worksheet, workbook order and original row lineage.
- Extracts follow-up dates and calculates their age at snapshot time.
- Creates a stable hash for change tracking.
- Exports Parquet, a formatted Excel workbook and a JSON quality report.
- Optionally loads the historical table into PostgreSQL.
- Includes deterministic sample generation, tests, linting and CI.

## Architecture

```mermaid
flowchart TD
    A["Dated Excel snapshots"] --> B["Discovery and date extraction"]
    B --> C["Five-sheet ingestion"]
    C --> D["Normalization and quality checks"]
    D --> E["Daily deduplication and lineage"]
    E --> F["Historical operations dataset"]
    F --> G["Parquet"]
    F --> H["Formatted Excel"]
    F --> I["PostgreSQL"]
    E --> J["JSON quality report"]
```

The pipeline never modifies source workbooks.

## Quick start

### 1. Create an environment

```bash
git clone https://github.com/Dummaia/historical-operations-data-pipeline.git
cd historical-operations-data-pipeline
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Generate safe sample snapshots

```bash
historical-pipeline generate-sample \
  --output data/sample \
  --snapshots 3 \
  --records 27
```

Each generated workbook contains the five expected worksheets:

1. `Overdue`
2. `0 to 7 Days`
3. `8 to 15 Days`
4. `16 to 25 Days`
5. `26 to 35 Days`

### 3. Run the pipeline

```bash
historical-pipeline run \
  --input data/sample \
  --output output \
  --config config/pipeline.toml
```

Expected result:

```text
Pipeline completed successfully
  Snapshots processed : 3
  Historical records  : 81
  Current processes   : 27
  Quality status      : PASSED
```

## Outputs

| File | Purpose |
| --- | --- |
| `historical_operations.parquet` | Typed, compressed analytical dataset |
| `historical_operations.xlsx` | Formatted history, current state, summary and issues |
| `quality_report.json` | Machine-readable run metrics and findings |

The Excel output contains:

- `history` — one process record per snapshot date;
- `latest_position` — the most recent state of each process;
- `summary` — counts by date, source file and worksheet;
- `quality_issues` — warnings, errors and informational controls.

## Minimum input contract

Column labels are converted to `UPPER_SNAKE_CASE`, so `Line Id`,
`LINE_ID` and `line-id` resolve to the same canonical name.

| Column | Type | Description |
| --- | --- | --- |
| `LINE_ID` | string | Stable identifier for a process line |
| `REQUEST_ID` | string | Parent request identifier |
| `CURRENT_STAGE` | string | Current workflow stage |
| `FOLLOW_UP_NOTES` | string | Latest operational note, optionally prefixed with a date |
| `SLA_DAYS_REMAINING` | nullable integer | Remaining SLA days; negative means overdue |
| `SLA_STATUS` | string | Human-readable SLA state |

See the complete [data dictionary](docs/data-dictionary.md).

## Lineage and daily state

Every ingested row receives `SNAPSHOT_DATE`, `SNAPSHOT_ORDER`,
`SOURCE_FILE`, `SOURCE_SHEET`, `SHEET_ORDER`, `SOURCE_ROW_NUMBER` and
`RECORD_HASH`.

When a process appears more than once on the same date, the pipeline sorts by
snapshot order, worksheet order and original row number, then keeps the last
appearance. This reconstructs a deterministic daily state without changing the
source evidence.

## PostgreSQL

```bash
pip install -e ".[postgres]"
docker compose up -d postgres

historical-pipeline run \
  --input data/sample \
  --output output \
  --config config/pipeline.toml \
  --database-url "postgresql+psycopg://pipeline:pipeline@localhost:5432/operations"
```

The default target is `analytics.historical_operations`. Example analysis is
available in [`sql/analytics_queries.sql`](sql/analytics_queries.sql).

> Docker credentials are development-only. Use a secret manager or
> environment-level credential injection outside local demonstrations.

## Python API

```python
from historical_operations_pipeline import load_config, run_pipeline

result = run_pipeline(
    "data/sample",
    output_dir="output",
    config=load_config("config/pipeline.toml"),
)

print(result.summary)
```

## Quality controls

Blocking checks include missing required columns, missing strict worksheets,
null process identifiers, invalid snapshot dates and duplicate daily states.
Non-blocking findings include missing follow-up notes, invalid optional SLA
values and future follow-up dates.

Read [`docs/quality-rules.md`](docs/quality-rules.md) for the full rule matrix.

## Tests and code quality

```bash
ruff check .
ruff format --check .
pytest --cov
```

GitHub Actions runs the suite on Python 3.11 and 3.12 for every push and pull
request.

## Repository structure

```text
.
├── .github/                    # CI, ownership and templates
├── config/pipeline.toml        # Data contract and output settings
├── data/sample/                # Generated fictitious workbooks
├── docs/                       # Architecture, dictionary and quality rules
├── examples/basic_usage.py     # Python API example
├── scripts/                    # Sample-data entry point
├── sql/                        # PostgreSQL schema and analytical queries
├── src/historical_operations_pipeline/
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Typed TOML configuration
│   ├── ingestion.py            # Discovery and workbook reading
│   ├── pipeline.py             # Orchestration
│   ├── quality.py              # Output invariants
│   ├── sample_data.py          # Deterministic synthetic data
│   ├── storage.py              # Parquet, Excel and PostgreSQL
│   └── transform.py            # Cleaning and history logic
└── tests/                      # Unit and end-to-end tests
```

## Engineering decisions

- **Parquet** provides compact, typed analytical storage.
- **Excel** keeps outputs accessible to operational teams.
- **PostgreSQL** enables reusable SQL analysis and downstream BI.
- **TOML** versions the data contract without another parser dependency.
- **Synthetic generation** makes the repository safe and reproducible.
- **Atomic replacement** reduces the risk of partial outputs.
- **Stable row hashing** enables efficient change detection.

## Roadmap

- S3 input/output adapter.
- Athena-compatible external table definition.
- Incremental PostgreSQL upserts.
- Data-quality trend dashboard.
- QuickSight-ready semantic views.

## Privacy

Never commit real operational spreadsheets, personal data, internal recipients,
credentials, private URLs or customer identifiers. See [`SECURITY.md`](SECURITY.md).

## Author

**Eduardo Maia** — Data Analytics, Business Intelligence and Process Automation

- [GitHub](https://github.com/Dummaia)
- [LinkedIn](https://www.linkedin.com/in/eduardomaia1)

## License

Distributed under the [MIT License](LICENSE).
