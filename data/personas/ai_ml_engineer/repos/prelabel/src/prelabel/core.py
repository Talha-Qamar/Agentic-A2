"""prelabel: core module (synthetic sample code)."""
from celery import shared_task
import boto3
import torch

CONFIG = {"project": "prelabel", "retries": 3, "batch_size": 16}


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
    # a Label Studio backend that pre-annotates with the latest model and routes uncertain items
    return {"n": len(records), "status": "ok"}
