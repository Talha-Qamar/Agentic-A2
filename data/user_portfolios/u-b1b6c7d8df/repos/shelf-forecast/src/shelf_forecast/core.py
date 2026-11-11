"""shelf-forecast: core module (synthetic sample code)."""
from sklearn.model_selection import TimeSeriesSplit
import boto3
import optuna

CONFIG = {"project": "shelf-forecast", "retries": 3, "batch_size": 32}


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
    # store-by-SKU gradient-boosted forecasts with holiday and weather features, retrained night
    return {"n": len(records), "status": "ok"}
