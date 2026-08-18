# Data dictionary

## Required source columns

| Column | Logical type | Nullable | Description |
| --- | --- | --- | --- |
| `LINE_ID` | string | No | Stable process-line identifier |
| `REQUEST_ID` | string | Yes | Parent request identifier |
| `CURRENT_STAGE` | string | Yes | Current workflow stage |
| `FOLLOW_UP_NOTES` | string | Yes | Latest progress note |
| `SLA_DAYS_REMAINING` | integer | Yes | Days until deadline; negative when overdue |
| `SLA_STATUS` | string | Yes | Operational SLA classification |

## Optional example columns

| Column | Logical type | Description |
| --- | --- | --- |
| `ITEM` | string | Generic requested item or service |
| `BUSINESS_AREA` | string | Originating business area |
| `COMPANY` | string | Fictitious organizational entity |
| `PROCESS_TYPE` | string | Process grouping |
| `START_DATE` | date | Process start date |
| `DUE_DATE` | date | Expected due date |

## Technical output columns

| Column | Logical type | Description |
| --- | --- | --- |
| `SNAPSHOT_DATE` | date | Reference date inferred from the filename |
| `SNAPSHOT_ORDER` | integer | Workbook order after deterministic sorting |
| `SOURCE_FILE` | string | Original workbook filename |
| `SOURCE_SHEET` | string | Canonical worksheet |
| `SHEET_ORDER` | integer | Configured worksheet order |
| `SOURCE_ROW_NUMBER` | integer | Original row position in Excel |
| `FOLLOW_UP_DATE` | date | First date extracted from the note |
| `FOLLOW_UP_AGE_DAYS` | integer | Snapshot date minus follow-up date |
| `RECORD_HASH` | string | Stable content hash for change detection |

## Date extraction

Snapshot filenames must contain either `YYYY-MM-DD` or `DD-MM-YYYY`. Dots and
underscores are also accepted as separators. Follow-up notes accept
`DD/MM/YYYY`, `DD-MM-YYYY` or day/month without a year.
