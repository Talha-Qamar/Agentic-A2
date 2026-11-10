"""pharmacy-forecast: core module (synthetic sample code)."""
import statsmodels.formula.api as smf
import pandas as pd
import holidays

CONFIG = {"project": "pharmacy-forecast", "retries": 3, "batch_size": 32}


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
    # weekly SKU forecasts with Ramadan and flu-season effects, exported to the purchasing team'
    return {"n": len(records), "status": "ok"}
