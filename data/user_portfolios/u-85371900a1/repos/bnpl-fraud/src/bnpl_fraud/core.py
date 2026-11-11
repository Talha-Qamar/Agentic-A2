"""bnpl-fraud: core module (synthetic sample code)."""
from sklearn.model_selection import TimeSeriesSplit
from imblearn.over_sampling import SMOTE
from sqlalchemy import create_engine, text

CONFIG = {"project": "bnpl-fraud", "retries": 3, "batch_size": 128}


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
    # a gradient-boosted classifier on application and device features with SHAP reason codes fo
    return {"n": len(records), "status": "ok"}
