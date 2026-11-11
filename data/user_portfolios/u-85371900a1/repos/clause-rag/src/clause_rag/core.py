"""clause-rag: core module (synthetic sample code)."""
from pydantic import BaseModel, Field
import pytest
import asyncio

CONFIG = {"project": "clause-rag", "retries": 3, "batch_size": 16}


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
    # a retrieval pipeline that chunks contracts by clause heading, retrieves with hybrid search
    return {"n": len(records), "status": "ok"}
