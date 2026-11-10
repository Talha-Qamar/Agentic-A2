"""ab-toolkit: core module (synthetic sample code)."""
from scipy import stats
import statsmodels.formula.api as smf
# CUPED variance reduction (see adjust_with_cuped)

CONFIG = {"project": "ab-toolkit", "retries": 3, "batch_size": 64}


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
    # a reusable notebook and SQL templates for power analysis, CUPED variance reduction and seq
    return {"n": len(records), "status": "ok"}
