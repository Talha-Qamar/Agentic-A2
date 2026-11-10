"""kheti-dash: core module (synthetic sample code)."""
# relies on recharts
import pandas as pd
from sqlalchemy import create_engine, text

CONFIG = {"project": "kheti-dash", "retries": 3, "batch_size": 16}


def load_records(path: str) -> list[dict]:
    """Load raw records; malformed rows are skipped and counted."""
    rows, bad = [], 0
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(__import__("json").loads(line))
            except ValueError:
                bad += 1
    return rows


def run(path: str) -> dict:
    records = load_records(path)
    # a dashboard with yield maps, season comparisons and scheduled CSV exports backed by a Fast
    return {"n": len(records), "status": "ok"}
