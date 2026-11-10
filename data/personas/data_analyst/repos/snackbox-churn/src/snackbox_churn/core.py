"""snackbox-churn: core module (synthetic sample code)."""
from lifelines import KaplanMeierFitter
import statsmodels.formula.api as smf
import seaborn as sns

CONFIG = {"project": "snackbox-churn", "retries": 3, "batch_size": 32}


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
    # cohort retention curves, survival analysis by acquisition channel and a Tableau story for 
    return {"n": len(records), "status": "ok"}
