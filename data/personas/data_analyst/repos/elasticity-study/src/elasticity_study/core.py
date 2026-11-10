"""elasticity-study: core module (synthetic sample code)."""
import statsmodels.formula.api as smf
# double ML style controls for promotions
import pandas as pd

CONFIG = {"project": "elasticity-study", "retries": 3, "batch_size": 64}


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
    # estimated price elasticity by category with controls for promotions and seasonality and si
    return {"n": len(records), "status": "ok"}
