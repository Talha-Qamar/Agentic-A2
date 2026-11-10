"""price-feeds: core module (synthetic sample code)."""
import requests
from pydantic import BaseModel, Field
import great_expectations as gx

CONFIG = {"project": "price-feeds", "retries": 3, "batch_size": 128}


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
    # a daily pipeline that pulls partner product feeds through their official APIs, validates t
    return {"n": len(records), "status": "ok"}
