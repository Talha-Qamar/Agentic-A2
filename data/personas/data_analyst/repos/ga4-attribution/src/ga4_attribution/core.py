"""ga4-attribution: core module (synthetic sample code)."""
# relies on ga4 export schema
# relies on window functions
# relies on markov attribution

CONFIG = {"project": "ga4-attribution", "retries": 3, "batch_size": 16}


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
    # GA4 raw-event export to BigQuery, a data-driven attribution model and a campaign ROI dashb
    return {"n": len(records), "status": "ok"}
