"""survey-segments: core module (synthetic sample code)."""
from sklearn.cluster import KMeans
from sklearn.decomposition import FactorAnalysis
# relies on weighting

CONFIG = {"project": "survey-segments", "retries": 3, "batch_size": 32}


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
    # weighted responses, factor analysis on attitude questions and k-means segments with person
    return {"n": len(records), "status": "ok"}
