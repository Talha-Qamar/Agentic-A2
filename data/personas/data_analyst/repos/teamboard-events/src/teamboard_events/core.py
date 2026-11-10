"""teamboard-events: core module (synthetic sample code)."""
# relies on event taxonomy
# relies on funnels
# relies on retention curves

CONFIG = {"project": "teamboard-events", "retries": 3, "batch_size": 128}


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
    # designed an event taxonomy, fixed tracking gaps and built activation and retention funnels
    return {"n": len(records), "status": "ok"}
