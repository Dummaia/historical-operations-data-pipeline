CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.historical_operations (
    snapshot_date date NOT NULL,
    snapshot_order integer NOT NULL,
    source_file text NOT NULL,
    source_sheet text NOT NULL,
    sheet_order integer NOT NULL,
    line_id text NOT NULL,
    request_id text,
    item text,
    business_area text,
    company text,
    process_type text,
    start_date date,
    due_date date,
    sla_days_remaining integer,
    sla_status text,
    current_stage text,
    follow_up_notes text,
    source_row_number integer NOT NULL,
    follow_up_date date,
    follow_up_age_days integer,
    record_hash text NOT NULL,
    PRIMARY KEY (snapshot_date, line_id)
);

CREATE INDEX IF NOT EXISTS idx_historical_operations_line_id
    ON analytics.historical_operations (line_id);

CREATE INDEX IF NOT EXISTS idx_historical_operations_request_id
    ON analytics.historical_operations (request_id);

CREATE INDEX IF NOT EXISTS idx_historical_operations_snapshot_date
    ON analytics.historical_operations (snapshot_date DESC);
