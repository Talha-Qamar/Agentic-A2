"""store-sites: core module (synthetic sample code)."""
from shapely.geometry import Point
import h3
# relies on census data

CONFIG = {"project": "store-sites", "retries": 3, "batch_size": 16}


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
    # catchment analysis combining census density, competitor locations and existing store sales
    return {"n": len(records), "status": "ok"}
