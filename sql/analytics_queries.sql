-- 1. Number of unique processes by snapshot date
SELECT
    snapshot_date,
    COUNT(DISTINCT line_id) AS unique_processes
FROM analytics.historical_operations
GROUP BY snapshot_date
ORDER BY snapshot_date;

-- 2. Current position of every process
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY line_id
            ORDER BY snapshot_date DESC, snapshot_order DESC,
                     sheet_order DESC, source_row_number DESC
        ) AS position_rank
    FROM analytics.historical_operations
)
SELECT *
FROM ranked
WHERE position_rank = 1
ORDER BY snapshot_date DESC, line_id;

-- 3. Overdue processes by current stage
WITH current_position AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY line_id
            ORDER BY snapshot_date DESC, snapshot_order DESC,
                     sheet_order DESC, source_row_number DESC
        ) AS position_rank
    FROM analytics.historical_operations
)
SELECT
    COALESCE(current_stage, 'NO STAGE') AS current_stage,
    COUNT(*) AS overdue_processes
FROM current_position
WHERE position_rank = 1
  AND sla_days_remaining < 0
GROUP BY COALESCE(current_stage, 'NO STAGE')
ORDER BY overdue_processes DESC, current_stage;

-- 4. Follow-ups older than three days in the current position
WITH current_position AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY line_id
            ORDER BY snapshot_date DESC, snapshot_order DESC,
                     sheet_order DESC, source_row_number DESC
        ) AS position_rank
    FROM analytics.historical_operations
)
SELECT
    line_id,
    request_id,
    current_stage,
    follow_up_date,
    follow_up_age_days
FROM current_position
WHERE position_rank = 1
  AND follow_up_age_days > 3
ORDER BY follow_up_age_days DESC, line_id;

-- 5. Detect state changes between consecutive snapshots
WITH changes AS (
    SELECT
        snapshot_date,
        line_id,
        current_stage,
        record_hash,
        LAG(record_hash) OVER (
            PARTITION BY line_id
            ORDER BY snapshot_date, snapshot_order,
                     sheet_order, source_row_number
        ) AS previous_hash
    FROM analytics.historical_operations
)
SELECT
    snapshot_date,
    line_id,
    current_stage
FROM changes
WHERE previous_hash IS NOT NULL
  AND record_hash <> previous_hash
ORDER BY snapshot_date, line_id;
