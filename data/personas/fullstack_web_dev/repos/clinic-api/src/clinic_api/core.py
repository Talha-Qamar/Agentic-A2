"""clinic-api: core module (synthetic sample code)."""
import redis
import pytest
from drf_spectacular.utils import extend_schema

CONFIG = {"project": "clinic-api", "retries": 3, "batch_size": 64}


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
    # a booking API with slot locking, SMS reminders sent from a worker queue and an admin panel
    return {"n": len(records), "status": "ok"}
