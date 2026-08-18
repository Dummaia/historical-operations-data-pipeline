"""Deterministic synthetic data for demonstrations and tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from historical_operations_pipeline.config import DEFAULT_SHEETS

BASE_SLA_VALUES = (-4, 1, 5, 9, 14, 19, 24, 29, 34)
STAGES = (
    "Intake",
    "Specification",
    "Market Analysis",
    "Negotiation",
    "Approval",
    "Contracting",
)
BUSINESS_AREAS = ("Operations", "Technology", "Facilities", "Finance")
COMPANIES = (
    "Northwind Logistics",
    "BluePeak Services",
    "Atlas Manufacturing",
    "Summit Retail",
)
ITEMS = (
    "Fleet maintenance service",
    "Network equipment",
    "Facility inspection",
    "Software subscription",
    "Safety equipment",
)


def classify_sheet(days_remaining: int) -> str:
    """Map an SLA value to the same five ranges consumed by the pipeline."""

    if days_remaining < 0:
        return "Overdue"
    if days_remaining <= 7:
        return "0 to 7 Days"
    if days_remaining <= 15:
        return "8 to 15 Days"
    if days_remaining <= 25:
        return "16 to 25 Days"
    return "26 to 35 Days"


def _snapshot_rows(
    *,
    snapshot_date: pd.Timestamp,
    snapshot_index: int,
    records: int,
) -> dict[str, list[dict[str, object]]]:
    sheets: dict[str, list[dict[str, object]]] = {name: [] for name in DEFAULT_SHEETS}

    for process_index in range(1, records + 1):
        days_remaining = BASE_SLA_VALUES[(process_index - 1) % len(BASE_SLA_VALUES)]
        days_remaining -= snapshot_index
        follow_up_age = (process_index + snapshot_index) % 6
        follow_up_date = snapshot_date - pd.Timedelta(days=follow_up_age)
        current_stage = STAGES[(process_index + snapshot_index) % len(STAGES)]

        notes: object = f"{follow_up_date:%d/%m/%Y} - {current_stage} reviewed in synthetic data."
        if process_index % 11 == 0 and snapshot_index == 0:
            notes = pd.NA

        row: dict[str, object] = {
            "LINE_ID": f"LINE-{process_index:04d}",
            "REQUEST_ID": f"REQ-{10_000 + process_index}",
            "ITEM": ITEMS[(process_index - 1) % len(ITEMS)],
            "BUSINESS_AREA": BUSINESS_AREAS[(process_index - 1) % len(BUSINESS_AREAS)],
            "COMPANY": COMPANIES[(process_index - 1) % len(COMPANIES)],
            "PROCESS_TYPE": "BACKLOG" if process_index % 7 == 0 else "STANDARD",
            "START_DATE": snapshot_date - pd.Timedelta(days=20 + process_index),
            "DUE_DATE": snapshot_date + pd.Timedelta(days=days_remaining),
            "SLA_DAYS_REMAINING": days_remaining,
            "SLA_STATUS": "OVERDUE" if days_remaining < 0 else "ON TIME",
            "CURRENT_STAGE": current_stage,
            "FOLLOW_UP_NOTES": notes,
        }
        sheets[classify_sheet(days_remaining)].append(row)

    return sheets


def generate_sample_snapshots(
    output_dir: str | Path,
    *,
    snapshots: int = 3,
    records: int = 27,
    start_date: str | pd.Timestamp = "2026-08-01",
) -> list[Path]:
    """Generate reproducible, fictitious multi-sheet Excel snapshots."""

    if snapshots < 1:
        raise ValueError("snapshots must be greater than zero")
    if records < len(BASE_SLA_VALUES):
        raise ValueError(f"records must be at least {len(BASE_SLA_VALUES)}")

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    first_date = pd.Timestamp(start_date).normalize()
    created: list[Path] = []

    for snapshot_index in range(snapshots):
        snapshot_date = first_date + pd.Timedelta(days=snapshot_index)
        sheets = _snapshot_rows(
            snapshot_date=snapshot_date,
            snapshot_index=snapshot_index,
            records=records,
        )
        target = directory / f"operations_snapshot_{snapshot_date:%Y-%m-%d}.xlsx"
        temporary = target.with_suffix(".tmp.xlsx")

        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            for sheet_name in DEFAULT_SHEETS:
                frame = pd.DataFrame(sheets[sheet_name])
                if frame.empty:
                    frame = pd.DataFrame(
                        columns=[
                            "LINE_ID",
                            "REQUEST_ID",
                            "ITEM",
                            "BUSINESS_AREA",
                            "COMPANY",
                            "PROCESS_TYPE",
                            "START_DATE",
                            "DUE_DATE",
                            "SLA_DAYS_REMAINING",
                            "SLA_STATUS",
                            "CURRENT_STAGE",
                            "FOLLOW_UP_NOTES",
                        ]
                    )
                frame.to_excel(writer, sheet_name=sheet_name, index=False)

        temporary.replace(target)
        created.append(target)

    return created
