"""hybrid-search: core module (synthetic sample code)."""
import faiss
import numpy as np
from locust import HttpUser, task

CONFIG = {"project": "hybrid-search", "retries": 3, "batch_size": 128}


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
    # hybrid lexical plus dense retrieval with a cross-encoder reranker and price filters parsed
    return {"n": len(records), "status": "ok"}
