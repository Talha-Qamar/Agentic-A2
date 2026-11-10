"""routemate-warehouse: core module (synthetic sample code)."""
# relies on airbyte
# relies on partitioning
# relies on service accounts

CONFIG = {"project": "routemate-warehouse", "retries": 3, "batch_size": 16}


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
    # ingested operational sources into BigQuery, modelled them in dbt and rebuilt the key repor
    return {"n": len(records), "status": "ok"}
