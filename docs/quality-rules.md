# Data-quality rules

| Code | Severity | Condition | Outcome |
| --- | --- | --- | --- |
| `NO_INPUT_FILES` | Error | No dated workbooks are discovered | Run blocked |
| `MISSING_WORKSHEET` | Error/Warning | Configured worksheet is absent | Depends on strict mode |
| `WORKSHEET_CONTRACT_FAILED` | Error | Required column is absent or names collide | Run blocked |
| `WORKBOOK_READ_FAILED` | Error | Workbook cannot be opened | Run blocked |
| `EMPTY_HISTORY` | Error | No historical rows remain | Run blocked |
| `NULL_PROCESS_ID` | Error | Output contains an empty process ID | Run blocked |
| `DUPLICATE_DAILY_PROCESS` | Error | More than one daily state remains | Run blocked |
| `INVALID_SNAPSHOT_DATE` | Error | Output contains a null snapshot date | Run blocked |
| `SNAPSHOT_DATE_NOT_FOUND` | Warning | Filename has no accepted date | File skipped |
| `FUTURE_FOLLOW_UP_DATE` | Warning | Note date is after snapshot date | Row retained |
| `INVALID_SLA_VALUE` | Warning | SLA value is not numeric | Row retained as null |
| `MISSING_FOLLOW_UP` | Info | Note is empty | Row retained |
| `DAILY_DUPLICATES_RESOLVED` | Info | Multiple same-day appearances exist | Latest retained |

The JSON report records discovered and processed files, processed worksheets,
raw rows, cleaned rows, historical rows, removed blank IDs, exact duplicates
and resolved daily duplicates.

`strict_sheets = true` is recommended for scheduled runs. For exploratory work,
the CLI supports `--no-strict-sheets`.
