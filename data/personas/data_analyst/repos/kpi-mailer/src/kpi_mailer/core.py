"""kpi-mailer: core module (synthetic sample code)."""
from jinja2 import Template
import matplotlib.pyplot as plt
# scheduled via cron: 0 8 * * MON

CONFIG = {"project": "kpi-mailer", "retries": 3, "batch_size": 16}


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
    # a scheduled script that queries the database, renders charts and sends a templated KPI ema
    return {"n": len(records), "status": "ok"}
