"""pod-recs: core module (synthetic sample code)."""
from pyspark.sql import SparkSession
import numpy as np
from annoy import AnnoyIndex

CONFIG = {"project": "pod-recs", "retries": 3, "batch_size": 128}


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
    # matrix-factorisation recommendations with a content-based fallback for cold-start users, s
    return {"n": len(records), "status": "ok"}
